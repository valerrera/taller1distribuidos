🧪 PLAN DE PRUEBAS COMPLETO (para sustentación)
🧠 Importante: cómo detener procesos entre pruebas

Cuando un servidor está corriendo en una terminal, para detenerlo usa:

✅ Ctrl + C

Después valida que el puerto quedó libre:

En coordinador:

ss -lntp | grep 5000 || echo "OK: 5000 libre"

En operaciones:

ss -lntp | grep 5001 || echo "OK: 5001 libre"
🔁 Orden recomendado para ejecutar el sistema (siempre igual)

Para cualquier prueba, el orden ideal es:

Levantar servidores de operación (op1/op2/op3)

Levantar coordinador

Ejecutar cliente

✅ PRUEBA 1 — Sistema completo (0 fallos)
Objetivo

Validar el flujo completo con los 3 servidores de operación activos.

Preparación (arranque limpio)

En cada servidor de operación:

op1 (10.43.99.136)
cd ~/sockets_distribuidos
python3 operation_server.py
op2 (10.43.99.139)
cd ~/sockets_distribuidos
python3 operation_server.py
op3 (10.43.97.155)
cd ~/sockets_distribuidos
python3 operation_server.py

En el coordinador (10.43.97.251):

cd ~/sockets_distribuidos
python3 coordinator.py

En el cliente (10.43.100.92):

cd ~/sockets_distribuidos
python3 client.py
Datos sugeridos

Ejemplo:

a = 1

b = -3

c = 2

Resultado esperado

El cliente imprime JSON con:

"ok": true

"dead_ops": [] (vacío)

"trace" mostrando qué servidor ejecutó cada operación (op1, op2, op3)

El coordinador muestra logs tipo:

[TRY] ... -> opX

[OK] ... resuelto por opX

Los servidores de operación muestran solicitudes recibidas y respuestas enviadas.

Evidencia (screenshots sugeridos)

Cliente con el JSON final.

Coordinador con logs [TRY]/[OK].

Al menos un servidor de operación mostrando que atendió una solicitud.

✅ Cómo pasar de Prueba 1 → Prueba 2

Sin apagar todo. Solo apaga 1 servidor de operación (op3) con Ctrl+C.

✅ PRUEBA 2 — Falla 1 servidor de operación (failover)
Objetivo

Apagar 1 servidor (op3) y verificar que el coordinador reintenta y resuelve igual.

Preparación (estado)

Deja corriendo:

op1 ✅

op2 ✅

op3 ❌ (apagado)

coordinador ✅

Apagar op3

En la VM op3 (10.43.97.155), en la terminal donde corre:
✅ Ctrl + C

Ejecución

En el cliente:

cd ~/sockets_distribuidos
python3 client.py
Resultado esperado

"ok": true

"dead_ops" contiene "op3" (o lo marca como caído)

En logs del coordinador:

intento con op3

timeout/fallo

reintento con op1 u op2 y éxito

Evidencia

Cliente JSON con dead_ops: ["op3"].

Coordinador mostrando FAIL con op3 y luego OK con otro.

✅ Cómo pasar de Prueba 2 → Prueba 3

Mantén op3 apagado y ahora apaga op2 con Ctrl+C.

✅ PRUEBA 3 — Falla 2 servidores (solo 1 vivo)
Objetivo

Dejar solo 1 servidor de operación vivo, y verificar que aún así se resuelve.

Preparación

op3 ❌ (apagado de Prueba 2)

op2 ❌ (apagar ahora)

op1 ✅ (debe quedar vivo)

coordinador ✅

Apagar op2

En la VM op2 (10.43.99.139):
✅ Ctrl + C

Ejecución

En el cliente:

cd ~/sockets_distribuidos
python3 client.py
Resultado esperado

"ok": true

"dead_ops" incluye op2 y op3

trace muestra que el único vivo resuelve varias operaciones.

Evidencia

Cliente JSON con 2 ops caídos.

Coordinador mostrando múltiples reintentos y que termina usando el único vivo.

Servidor vivo mostrando varias solicitudes.

✅ Cómo pasar de Prueba 3 → Prueba 4

Ahora apaga también el último servidor vivo (op1) con Ctrl+C.

✅ PRUEBA 4 — Falla total (3 servidores caídos)
Objetivo

Confirmar qué ocurre cuando no hay servidores de operación disponibles.

Preparación

Apaga op1:

En op1 (10.43.99.136):
✅ Ctrl + C

Deja:

coordinador ✅

op1/op2/op3 ❌ (todos apagados)

Ejecución

En cliente:

cd ~/sockets_distribuidos
python3 client.py
Resultado esperado

Ideal: "ok": false o error controlado

dead_ops lista los 3

El coordinador NO se cae (solo reporta fallo)

Evidencia

Cliente mostrando fallo controlado.

Coordinador mostrando intentos y fallos en todos.

✅ Cómo pasar de Prueba 4 → Prueba 5

Vuelve a encender op1 (solo uno), para probar puerto ocupado.

✅ PRUEBA 5 — Puerto ocupado (doble ejecución)
Objetivo

Mostrar que si ejecutas 2 veces operation_server.py en la misma VM, falla el bind por puerto ocupado.

Preparación

En op1 (10.43.99.136) levanta 1 vez:

cd ~/sockets_distribuidos
python3 operation_server.py
Ejecución

En op1, en otra terminal (o separada), vuelve a ejecutar:

cd ~/sockets_distribuidos
python3 operation_server.py
Resultado esperado

Error tipo:

Address already in use

ss muestra el puerto ocupado:

ss -lntp | grep 5001
Evidencia

Screenshot del error.

Screenshot del ss -lntp.

✅ Cómo pasar de Prueba 5 → Prueba 6

Apaga todas las instancias duplicadas, dejando 0 o 1 viva según necesites:
✅ Ctrl+C en la que no usarás.

✅ PRUEBA 6 — Entrada inválida en cliente
Objetivo

Probar validación ante entradas inválidas (texto, vacío, etc.).

Ejecución

En cliente:

cd ~/sockets_distribuidos
python3 client.py

Cuando pida a, ingresa:

hola (texto)
o deja vacío y Enter.

Resultado esperado (ideal)

Error controlado o repregunta

El cliente no debería colapsar sin mensaje.

Evidencia

Screenshot del comportamiento (mensaje de error o validación).

✅ PRUEBA 7 — Caso especial: discriminante negativo
Objetivo

Probar comportamiento cuando la ecuación no tiene raíces reales.

Ejecución

En cliente:

cd ~/sockets_distribuidos
python3 client.py

Datos:

a = 1

b = 0

c = 1 (discriminante = -4)

Resultado esperado

Depende de la implementación:

Si no soporta complejos: "ok": false con mensaje

Si soporta complejos: devuelve raíces complejas

Evidencia

Cliente + coordinador mostrando el manejo del caso.

🧹 Cómo apagar todo al final (para dejar listo para mañana)

En cada VM donde esté corriendo algo:
✅ Ctrl + C

Luego verifica:

Coordinador:

ss -lntp | grep 5000 || echo "OK: coordinador apagado"

Operaciones:

ss -lntp | grep 5001 || echo "OK: operación apagada"
🧾 Checklist final para la sustentación

✅ Archivos correctos en cada VM (~/sockets_distribuidos)
✅ Coordinador con IPs correctas (op1/op2/op3)
✅ Prueba 1 funcionando con 0 fallos
✅ Prueba 2 funcionando con 1 fallo
✅ Prueba 3 funcionando con 2 fallos
✅ Prueba 4 mostrando fallo controlado con 3 fallos
✅ Evidencias (screenshots) de logs y salidas del cliente
