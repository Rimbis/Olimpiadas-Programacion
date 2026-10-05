-- =====================================================================
-- AEROPLATE - Ajustes de tablas y funciones de negocio (Supabase)
-- Ejecutar completo en Supabase > SQL Editor. Se puede correr varias veces.
--
-- Estados de compras:
--   pendiente  -> creada, esperando pago (vence a los 15 min)
--   pagada     -> cobrada, pendiente de entrega
--   entregada  -> entregada por ventas (queda en historial_ventas)
--   vencida    -> pasaron 15 min sin pagar (libera asientos)
--   cancelada  -> cancelada por el cliente estando pendiente
--   anulada    -> anulada por ventas
--
-- ANTES de correr, revisar (opcional):
--   select proname, pg_get_function_arguments(oid) from pg_proc
--   where proname in ('crear_compra','vencer_compras','cancelar_compra');
--   select conname, pg_get_constraintdef(oid) from pg_constraint
--   where conrelid = 'compras'::regclass;   -- ¿hay un CHECK sobre estado?
-- Si hay un CHECK de estado, agregarle los valores de arriba.
-- =====================================================================

-- ---------- 1. Ajustes de tablas ----------

-- Número de pedido correlativo.
create sequence if not exists seq_numero_pedido start 1001;

-- La letra del asiento es texto (A-Z), no INT como decía el DER.
alter table asiento alter column letra type varchar(2) using letra::text;

-- Un asiento no puede repetirse en el mismo vuelo. Si falla por duplicados,
-- borrar los asientos de prueba: delete from asiento;
create unique index if not exists asiento_unico_por_vuelo
    on asiento (id_vuelo, fila, letra);

-- Id del pago en la pasarela (evita registrar dos veces la misma notificación).
alter table pagos add column if not exists id_externo varchar(60);
create unique index if not exists pagos_externo_estado_uq
    on pagos (id_externo, estado) where id_externo is not null;

-- contactos_empresa.id y mails.id_contacto son UUID. id_contacto es opcional
-- (el mail al cliente no tiene contacto) y archivo_adjunto tambien (aun no se usan).
do $$
begin
    if exists (
        select 1 from information_schema.columns
        where table_schema = 'public' and table_name = 'mails'
          and column_name = 'id_contacto' and data_type <> 'uuid'
    ) then
        alter table mails drop column id_contacto;
        alter table mails add column id_contacto uuid references contactos_empresa (id);
    end if;
end $$;
alter table mails alter column id_contacto drop not null;
alter table mails alter column archivo_adjunto drop not null;

-- ---------- 2. Limpiar versiones viejas ----------
drop function if exists crear_compra(uuid, integer, jsonb);
drop function if exists modificar_compra(integer, uuid, jsonb);
drop function if exists cancelar_compra(integer, uuid);
drop function if exists vencer_compras();

-- ---------- 3. Funciones auxiliares ----------

-- Libera (borra) los asientos de las compras indicadas.
create or replace function _liberar_asientos(p_ids integer[])
returns void language plpgsql as $$
begin
    delete from asiento
    where id_pasajero_reserva in (
        select id from pasajeros_reserva where id_compra = any(p_ids)
    );
end $$;

-- Inserta los pasajeros de una compra y reserva su asiento en el vuelo.
-- Si un asiento ya está ocupado, lanza unique_violation (23505).
create or replace function _insertar_pasajeros(
    p_id_compra integer, p_id_vuelo integer, p_pasajeros jsonb
) returns void language plpgsql as $$
declare
    p jsonb;
    v_id_pasajero integer;
begin
    for p in select * from jsonb_array_elements(p_pasajeros) loop
        insert into pasajeros_reserva
            (id_compra, nombre, apellido, dni, tipo_pasajero,
             condiciones_medicas, descripcion_medica)
        values
            (p_id_compra, p->>'nombre', p->>'apellido', (p->>'dni')::integer,
             p->>'tipo_pasajero',
             coalesce((p->>'condiciones_medicas')::boolean, false),
             nullif(p->>'descripcion_medica', ''))
        returning id into v_id_pasajero;

        insert into asiento (letra, fila, id_pasajero_reserva, id_vuelo)
        values (upper(p->>'letra'), (p->>'fila')::integer, v_id_pasajero, p_id_vuelo);
    end loop;
end $$;

-- ---------- 4. DFD 3.6 / 3.7: vencimiento de compras ----------

-- Pasa a 'vencida' las compras pendientes de más de 15 minutos, libera sus
-- asientos y devuelve los ids vencidos (para avisar por mail).
create or replace function vencer_compras()
returns integer[] language plpgsql as $$
declare
    v_ids integer[];
begin
    with v as (
        update compras set estado = 'vencida'
        where estado = 'pendiente' and fecha < now() - interval '15 minutes'
        returning id
    )
    select coalesce(array_agg(id), '{}'::integer[]) into v_ids from v;

    perform _liberar_asientos(v_ids);
    return v_ids;
end $$;

-- ---------- 5. DFD 2 / 3.1: crear compra ----------

-- Crea compra + detalle + pasajeros + asientos. precio_total del paquete es
-- el precio POR PASAJERO; el total de la compra es precio * cantidad.
create or replace function crear_compra(
    p_id_cliente uuid, p_id_paquete integer, p_pasajeros jsonb
) returns jsonb language plpgsql as $$
declare
    v_paquete paquetes_turisticos%rowtype;
    v_cant    integer := jsonb_array_length(p_pasajeros);
    v_id      integer;
    v_numero  integer;
    v_total   numeric(12,2);
begin
    select * into v_paquete from paquetes_turisticos where id = p_id_paquete;
    if not found then raise exception 'PAQUETE_INEXISTENTE'; end if;
    if v_paquete.id_vuelo is null then raise exception 'PAQUETE_SIN_VUELO'; end if;

    v_total  := v_paquete.precio_total * v_cant;
    v_numero := nextval('seq_numero_pedido');

    insert into compras (numero_pedido, id_cliente, fecha, precio_total, estado)
    values (v_numero, p_id_cliente, now(), v_total, 'pendiente')
    returning id into v_id;

    insert into detalle_compras
        (id_compra, tipo_item, cantidad_pasajeros, id_paquete, precio_unitario, subtotal)
    values (v_id, 'paquete', v_cant, p_id_paquete, v_paquete.precio_total, v_total);

    perform _insertar_pasajeros(v_id, v_paquete.id_vuelo, p_pasajeros);

    return jsonb_build_object(
        'id', v_id, 'numero_pedido', v_numero, 'estado', 'pendiente',
        'precio_total', v_total, 'vence_en_minutos', 15);
end $$;

-- ---------- 6. DFD 4.2: modificar pedido pendiente ----------

-- Reemplaza los pasajeros y asientos de un pedido pendiente y recalcula el total.
create or replace function modificar_compra(
    p_id_compra integer, p_id_cliente uuid, p_pasajeros jsonb
) returns jsonb language plpgsql as $$
declare
    v_compra  compras%rowtype;
    v_detalle detalle_compras%rowtype;
    v_vuelo   integer;
    v_cant    integer := jsonb_array_length(p_pasajeros);
    v_total   numeric(12,2);
begin
    select * into v_compra from compras
    where id = p_id_compra and id_cliente = p_id_cliente for update;
    if not found then raise exception 'COMPRA_INEXISTENTE'; end if;
    if v_compra.estado <> 'pendiente' then raise exception 'NO_PENDIENTE'; end if;

    select * into v_detalle from detalle_compras where id_compra = p_id_compra limit 1;
    select id_vuelo into v_vuelo from paquetes_turisticos where id = v_detalle.id_paquete;

    perform _liberar_asientos(array[p_id_compra]);
    delete from pasajeros_reserva where id_compra = p_id_compra;
    perform _insertar_pasajeros(p_id_compra, v_vuelo, p_pasajeros);

    v_total := v_detalle.precio_unitario * v_cant;
    update detalle_compras set cantidad_pasajeros = v_cant, subtotal = v_total
    where id_compra = p_id_compra;
    update compras set precio_total = v_total where id = p_id_compra;

    return jsonb_build_object(
        'id', p_id_compra, 'numero_pedido', v_compra.numero_pedido,
        'estado', 'pendiente', 'precio_total', v_total);
end $$;

-- ---------- 7. DFD 4.3: cancelar pedido pendiente ----------
create or replace function cancelar_compra(p_id_compra integer, p_id_cliente uuid)
returns void language plpgsql as $$
declare
    v_estado text;
begin
    select estado into v_estado from compras
    where id = p_id_compra and id_cliente = p_id_cliente for update;
    if not found then raise exception 'COMPRA_INEXISTENTE'; end if;
    if v_estado <> 'pendiente' then raise exception 'NO_PENDIENTE'; end if;

    perform _liberar_asientos(array[p_id_compra]);
    update compras set estado = 'cancelada' where id = p_id_compra;
end $$;

-- ---------- 8. DFD 3.4 / 3.5: registrar pago y actualizar compra ----------

-- Registra el pago y, si fue aprobado, pasa la compra a 'pagada'.
-- Devuelve true solo cuando ESTA llamada dejó la compra pagada.
-- Es idempotente: la misma notificación repetida no se registra dos veces.
create or replace function confirmar_pago(
    p_id_compra integer, p_monto numeric, p_metodo text,
    p_estado_pago text, p_id_externo text
) returns boolean language plpgsql as $$
declare
    v_estado text;
begin
    select estado into v_estado from compras where id = p_id_compra for update;
    if not found then raise exception 'COMPRA_INEXISTENTE'; end if;

    if p_id_externo is not null and exists (
        select 1 from pagos where id_externo = p_id_externo and estado = p_estado_pago
    ) then
        return false;
    end if;

    insert into pagos (id_compra, monto, metodo_pago, fecha, estado, id_externo)
    values (p_id_compra, p_monto, p_metodo, now(), p_estado_pago, p_id_externo);

    if p_estado_pago = 'aprobado' and v_estado = 'pendiente' then
        update compras set estado = 'pagada' where id = p_id_compra;
        return true;
    end if;
    return false;
end $$;

-- ---------- 9. DFD 5.4: entregar pedido ----------
-- Pasa de 'pagada' a 'entregada' y lo registra en historial_ventas.
create or replace function entregar_compra(p_id_compra integer, p_id_admin uuid)
returns void language plpgsql as $$
declare
    v_compra compras%rowtype;
begin
    select * into v_compra from compras where id = p_id_compra for update;
    if not found then raise exception 'COMPRA_INEXISTENTE'; end if;
    if v_compra.estado <> 'pagada' then raise exception 'NO_ENTREGABLE'; end if;

    update compras set estado = 'entregada' where id = p_id_compra;
    insert into historial_ventas (id_compra, id_cliente, id_admin, monto_total, fecha)
    values (v_compra.id, v_compra.id_cliente, p_id_admin, v_compra.precio_total, now());
end $$;

-- ---------- 10. DFD 5.5: anular pedido ----------
-- Anula un pedido pendiente o pagado y libera sus asientos.
-- (Si estaba pagado, el reintegro del dinero se hace a mano en Mercado Pago.)
create or replace function anular_compra(p_id_compra integer)
returns void language plpgsql as $$
declare
    v_estado text;
begin
    select estado into v_estado from compras where id = p_id_compra for update;
    if not found then raise exception 'COMPRA_INEXISTENTE'; end if;
    if v_estado not in ('pendiente', 'pagada') then raise exception 'NO_ANULABLE'; end if;

    perform _liberar_asientos(array[p_id_compra]);
    update compras set estado = 'anulada' where id = p_id_compra;
end $$;

-- ---------- 11. Seguridad ----------
-- Supabase expone las funciones por la API con la clave anon (que ve el
-- navegador). Se las quitamos: solo el backend (service_role) puede usarlas.
revoke all on function _liberar_asientos(integer[])                          from public, anon, authenticated;
revoke all on function _insertar_pasajeros(integer, integer, jsonb)          from public, anon, authenticated;
revoke all on function vencer_compras()                                      from public, anon, authenticated;
revoke all on function crear_compra(uuid, integer, jsonb)                    from public, anon, authenticated;
revoke all on function modificar_compra(integer, uuid, jsonb)                from public, anon, authenticated;
revoke all on function cancelar_compra(integer, uuid)                        from public, anon, authenticated;
revoke all on function confirmar_pago(integer, numeric, text, text, text)    from public, anon, authenticated;
revoke all on function entregar_compra(integer, uuid)                        from public, anon, authenticated;
revoke all on function anular_compra(integer)                                from public, anon, authenticated;
