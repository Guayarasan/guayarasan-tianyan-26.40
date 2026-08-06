# Tianyan 1.2.3.3 → 1.2.3.4 — Registro de cambios

## 1. Pistones y flujo de líquidos: eliminados por completo
`onPistonExtend`, `onPistonRetract` y `onBlockFromTo` (flujo natural de agua/lava)
ahora son no-ops reales: nunca construyen un `LogData` ni lo insertan en la
caché/base de datos. Se mantienen registrados en Endstone (por compatibilidad
de API) pero no hacen nada.

**Importante:** colocar/recoger agua o lava CON CUBETA sigue registrándose
normalmente, porque eso pasa por `onBlockPlace`/`onBlockBreak` (eventos
disparados por el jugador), no por `onBlockFromTo` (que solo cubre la
propagación automática entre bloques).

**Impacto:** en un servidor con granjas automáticas, esto es probablemente la
mayor reducción de volumen de la base de datos de todo el cambio — estos dos
tipos de evento suelen ser, con diferencia, los más numerosos.

## 2. Filtro centralizado (`no_log_mobs` + `no_log_blocks`)
Nuevo módulo `event_filter.h/.cpp`, con un `unordered_set` (O(1)) reconstruido
cada vez que se carga la configuración. Todos los eventos relevantes lo
consultan ANTES de construir el `LogData`.

- **Bug corregido en `no_log_mobs`:** antes solo se ignoraba un mob si **no**
  tenía NameTag. Un zombie con nombre puesto igual se registraba. Ahora se
  ignora siempre que su tipo esté en la lista, sin importar NameTag,
  CustomName, Variant ni cualquier otro dato.
- **Nuevo `no_log_blocks`:** acepta `"minecraft:stone"` o `"stone"`,
  case-insensitive. Se aplica en `onBlockBreak`, `onBlockPlace` y clic
  derecho en bloque. Se añade con valor por defecto `[]`, y la migración
  automática de config existente lo agrega sin tocar el resto de tu
  configuración.

## 3. Shulker Box y contenedores
Endstone 0.11.5 **no tiene ningún evento dedicado de apertura de
inventario/contenedor** (lo verifiqué contra el código fuente del SDK). El
único gancho disponible es `PlayerInteractEvent`, el mismo que ya usan los
cofres. Antes, el registro solo ocurría si `getBlockStates()` no estaba
vacío; ahora se fuerza el registro para una lista explícita de bloques
contenedor (chest, barrel, shulker_box de cualquier color, dispenser,
dropper, hopper, furnace, smoker, brewing_stand, lectern, beacon,
decorated_pot, campfire, lodestone, respawn_anchor, bell), sin depender de
que el estado del bloque venga o no vacío.

**Limitación honesta:** si el problema original era un bug específico de
Endstone al despachar `PlayerInteractEvent` para Shulker Box, esta es la
única vía disponible en la API actual para intentar cubrirlo; no hay forma
de verificarlo sin un servidor Bedrock real.

## 4. Nuevo evento: `vehicle_destroy`
`ActorDeathEvent` de Endstone solo se dispara para `Mob` (criaturas vivas).
Minecarts, botes, Item Frames y Armor Stands pueden desaparecer sin dejar
ningún rastro. Se añadió un listener de `ActorRemoveEvent`, filtrado
estrictamente a estos tipos (minecart, boat, item_frame, armor_stand) para
no generar ruido — `ActorRemoveEvent` se dispara para *cualquier* entidad
que desaparece (drops, orbes de XP, proyectiles...).

**Limitación real, no resuelta:** no existe en Endstone 0.11.5 un evento
equivalente a `InventoryMoveItemEvent` para detectar transferencias de
Hopper. No se implementó nada al respecto para no simular una función que no
se puede verificar.

## 5. Traducción al español
- `language/es_ES.json` (servidor) y `WebUI/languages/es_ES.json` (panel
  web) traducidos completos, incluyendo claves nuevas (`vehicle_destroy`) y
  5 claves de arranque que **no estaban traducidas en NINGÚN idioma**
  original del proyecto (`Config file created`, etc. — se agregaron también
  a en_US/zh_CN/ru_RU para no dejar la brecha solo a medias).
- Config por defecto ahora usa `es_ES` para instalaciones **nuevas**. Una
  instalación existente conserva su idioma actual (la migración de config
  solo agrega claves que faltan, nunca sobrescribe `language`).
- WebUI (`index.html`, `script.js`, `style.css`, `server.py`): selector de
  idioma con opción Español, todos los textos de respaldo (los que se ven
  antes de que cargue el JS) traducidos, y todos los mensajes de error /
  logs / comentarios del backend Python traducidos.
- Comentarios en español en `event_listener.cpp`, `event_listener.h`,
  `tianyan_plugin.cpp` y `tianyan_core.h` (los archivos que modifiqué).

**Limitación de alcance:** los comentarios en chino de archivos que NO
toqué funcionalmente (`database.hpp`, `menu.cpp`, `tianyan_protect.cpp`,
`rust_backend.cpp`, `sqlite_backend.cpp`, y algunos headers) siguen sin
traducir — son ~350 líneas de comentarios que no afectan lo que ve un
jugador o admin en el juego/consola/WebUI. Si quieres que los traduzca
también, lo hago en una siguiente pasada.

## 6. Verificación de compilación
Este entorno no tiene acceso a un rustc lo bastante nuevo para compilar el
crate `rust_mysql` (dependencia transitiva pide `edition2024`), así que no
pude producir un `.so` final enlazado. Sí pude:
- Descargar y configurar el proyecto real con CMake + Endstone v0.11.5 +
  fmt + nlohmann_json + endstone_inventoryui (las mismas versiones que
  especifica tu `CMakeLists.txt`).
- Compilar `event_listener.cpp`, `tianyan_plugin.cpp`, `event_filter.cpp`,
  `tianyan_core.cpp` y el resto de `.cpp` del proyecto con
  `-fsyntax-only` usando exactamente los flags e includes reales que
  usaría tu build — **cero errores, cero warnings** en todos los archivos.

Esto da bastante confianza en que el código es correcto a nivel de tipos y
sintaxis contra la API real de Endstone, pero no reemplaza una prueba en un
servidor Bedrock real con tráfico real.

## Archivos nuevos
- `include/event_filter.h`, `src/event_filter.cpp`
- `language/es_ES.json`, `WebUI/languages/es_ES.json`

## Archivos modificados
- `include/tianyan_core.h`, `include/event_listener.h`
- `src/event_listener.cpp`, `src/tianyan_plugin.cpp`
- `language/en_US.json`, `language/zh_CN.json`, `language/ru_RU.json`
  (solo se agregaron las 6 claves que faltaban, sin tocar traducciones
  existentes)
- `WebUI/index.html`, `WebUI/script.js`, `WebUI/style.css`,
  `WebUI/server.py`
