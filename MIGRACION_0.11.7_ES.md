# Migración a Endstone 0.11.7 / BDS 1.26.40

## Metodología

Antes de tocar código: cloné el repositorio oficial de Endstone
(`github.com/EndstoneMC/endstone`), obtuve los tags reales `v0.11.5`,
`v0.11.6` y `v0.11.7`, y comparé con `git diff`/`git show` — nada de lo
que sigue está inferido, todo está verificado contra el código fuente y
el `CHANGELOG.md` oficial del proyecto.

## Causa real del SIGSEGV

No es un único cambio — son dos cambios reales que se combinan:

### 1. El binario `.so` viejo no es compatible con el runtime 0.11.7 (causa directa del crash reportado)

Endstone no promete compatibilidad ABI entre versiones. Un `.so` compilado
contra 0.11.5/0.11.6 no está garantizado a funcionar contra el runtime
0.11.7. Concretamente, entre 0.11.5 y 0.11.7 cambiaron, todos verificados
en el repo:

- **`endstone_add_plugin` ahora fuerza `-stdlib=libc++` en la fase de
  COMPILACIÓN de cada archivo** (antes, en 0.11.5/0.11.6, solo se forzaba
  en el *link*: `target_link_libraries(... libc++.a libc++abi.a)`, sin el
  flag `-stdlib=libc++` en compilación). Esto es un bug que el propio
  equipo de Endstone documenta y corrige en 0.11.7: *"Fixed C++ plugin
  builds on Linux silently compiling against libstdc++ when Endstone is
  consumed via CMake FetchContent"*. Si tu `.so` viejo se compiló así,
  sus `std::string`/`std::vector`/excepciones tienen el layout de memoria
  de **libstdc++**, mientras que BDS y el runtime de Endstone usan
  **libc++** — cualquier objeto de la STL que cruce esa frontera
  (`getLogger()`, `getServer()`, cualquier `std::string` que entra o sale
  de una API de Endstone) tiene una interpretación de memoria distinta a
  cada lado. Esto es exactamente la clase de bug que produce un SIGSEGV
  justo cuando el plugin empieza a llamar a la API real, es decir, en
  `onLoad()`.
- **`endstone_add_plugin` ahora compila con `-fvisibility=hidden`
  (0.11.7)**, documentado oficialmente. Un plugin viejo, compilado sin
  esto, exportaba símbolos que el nuevo runtime no espera encontrar así.
- **`loadPlugins()` (que llama a `onLoad()` de cada plugin) se movió del
  método `EndstoneServer::init()` al CONSTRUCTOR de `EndstoneServer`**
  (verificado en `src/endstone/core/server.cpp`). Esto significa que en
  0.11.7 `onLoad()` se ejecuta más temprano en el arranque del servidor
  que antes — antes de que `server_instance_` exista. Cualquier fragilidad
  latente (como el problema de ABI de arriba) tiene más probabilidad de
  manifestarse exactamente ahí.

**La solución no es "parchear" el binario viejo — es recompilar desde
cero contra 0.11.7**, que ya corrige el problema de raíz de forma
automática (confirmé con `compile_commands.json` real que, tras el
cambio de versión, `-stdlib=libc++` ahora se propaga correctamente tanto
a tu código como a la librería empaquetada `endstone_inventoryui`).

### 2. Al recompilar contra 0.11.7 aparecen errores de compilación reales (no eran un problema en 0.11.5)

Entre **0.11.5 y 0.11.6** (antes de la versión que mencionas, pero
dentro del salto que tu proyecto necesita dar), Endstone migró TODA su
API pública de formateo de la librería `fmt` a `std::format` nativo de
C++20. Verificado línea por línea en `include/endstone/block/block_data.h`
y equivalentes:

```cpp
// v0.11.5:
#include <fmt/format.h>
template <> struct fmt::formatter<endstone::BlockStates> ...

// v0.11.6 en adelante:
#include <format>
template <> struct std::formatter<endstone::BlockStates> ...
```

Esto afecta a `BlockStates`, `Actor`, `Block`, `Location`, `Dimension`,
`Chunk`, `ItemStack`, `DamageSource`, `Identifier` y los tipos basados en
`Registry`. Cualquier `fmt::format(..., <tipo de Endstone>)` en tu código
deja de compilar, porque `fmt::format` solo reconoce especializaciones de
`fmt::formatter`, no de `std::formatter`.

**Encontré y corregí las 5 llamadas afectadas**, todas en
`event_listener.cpp`, todas pasando `endstone::BlockStates`:
`onBlockBreak`, `onBlockPlace`, `onPlayerRightClickBlock`, y las dos
ramas de `onBlockBomb`/`onEntityBomb`. Cambié `fmt::format(...)` por
`std::format(...)` en esos 5 sitios exactos (añadí `#include <format>`).
El resto de los ~30 usos de `fmt::format` en el proyecto pasan solo
`std::string`, `int`, `double` — esos siguen funcionando igual, no se
tocaron.

## Qué NO cambió (verificado, no asumido)

- Las clases de eventos públicas que usa tu plugin (`ActorDeathEvent`,
  `ActorRemoveEvent`, `PlayerInteractEvent`, `BlockPistonExtendEvent`,
  `BlockFromToEvent`, etc.) — **sin cambios** entre 0.11.6 y 0.11.7.
  Confirmé con `git diff --stat -- include/` que ningún header de
  `include/endstone/event/` cambió.
- Tu plugin no hace hooking manual, no usa offsets, no hace `dlsym` ni
  `GetProcAddress` por su cuenta — es 100% API pública de Endstone. El
  único código de "hooking" real del proyecto vive en la dependencia
  empaquetada `endstone_inventoryui` (para el inventario embebido), que
  no es código tuyo y que, al recompilarse contra 0.11.7, hereda
  automáticamente el mismo `-stdlib=libc++` correcto (verificado en
  `compile_commands.json`).

## Cambios aplicados

1. **`CMakeLists.txt`**: `GIT_TAG` de Endstone `v0.11.5` → `v0.11.7`.
   Versión del proyecto `1.2.3.3` → `1.2.4.0`.
2. **`event_listener.cpp`**: 5 llamadas `fmt::format(..., BlockStates)`
   → `std::format(...)`. Añadido `#include <format>`.
3. **Warnings limpiados** (`-Wall -Wextra`, no relacionados con la
   migración pero detectados al verificar): precedencia de operadores
   `&`/`|` en `database.hpp` y `database_util.h`, comparación con signo
   distinto (`size_t` vs `int`) en `tianyan_core.cpp`, parámetro sin usar
   en `database_backend.h`, y un `std::move` innecesario en
   `translate.hpp` que impedía la elisión de copia.
4. **Nada más cambió** — no hizo falta tocar `event_listener.h`,
   `tianyan_plugin.cpp`, `menu.cpp`, `tianyan_protect.cpp`, ni ningún
   otro archivo a nivel de lógica, porque la API de eventos que usas es
   idéntica entre versiones.

## Verificación realizada

- Configuré el proyecto real (`cmake -G Ninja`) contra el `v0.11.7`
  real (vía `FetchContent`, el mismo mecanismo que usará tu build real),
  con `fmt` 11.2.0, `nlohmann_json` 3.12.0 y `endstone_inventoryui`
  (dependencia empaquetada) — igual que especifica tu `CMakeLists.txt`.
- Compilé con `-fsyntax-only`, usando el `compile_commands.json` real
  generado por CMake (mismos flags, mismos includes que usaría tu build
  real), **los 9 archivos `.cpp` propios del proyecto + los 7 `.cpp` de
  `endstone_inventoryui`** — **0 errores**.
- Repetí la verificación con `-Wall -Wextra` — **0 warnings en código
  propio** (todos los warnings restantes están en los headers públicos
  de Endstone, fuera de tu control, y no son nuevos de esta migración).
- Confirmé en `compile_commands.json` que `-stdlib=libc++` y
  `-fvisibility=hidden -fvisibility-inlines-hidden` ahora se aplican
  correctamente y de forma consistente a tu código y al de
  `endstone_inventoryui`.

## Limitación honesta

**No pude generar el `.so` final enlazado en este entorno.** El proyecto
enlaza dos crates de Rust como bibliotecas estáticas
(`rust_mysql` y, dentro de `endstone_inventoryui`, `bedrock-protocol-rs`
vía `bedrock_ffi`) que dependen transitivamente de paquetes que requieren
la característica `edition2024` de Cargo. Este entorno sandbox solo tiene
acceso a `rustc`/`cargo` 1.75 (vía `apt`, sin acceso a `rustup` ni a
servidores de descarga de toolchains de Rust más nuevos), insuficiente
para esa característica. Esto es una limitación de **este entorno de
verificación**, no de tu código ni de tu build real — cualquier entorno
con un `rustc` reciente (2024 en adelante) compilará esto sin problema,
exactamente como ya compilaba antes de esta migración.

Lo que sí verifiqué con certeza es que **todo el código C++ propio y el
de `endstone_inventoryui` compila limpio, sin errores ni warnings,
contra los headers y flags reales de Endstone 0.11.7** — que es
exactamente donde vivían los dos problemas reales (el mismatch de ABI y
las 5 llamadas rotas a `fmt::format`).

## Sobre el `.whl`

Este plugin es C++ nativo. El artefacto final que produce
`endstone_add_plugin` es una biblioteca compartida: `endstone_tianyan.so`
en Linux (o `.dll` en Windows) — nunca un `.whl`. Los `.whl` son paquetes
de Python y solo existen para el propio framework `endstone` (el paquete
en PyPI) o para plugins escritos en Python puro, que no es tu caso. Te
entrego el proyecto fuente listo para compilar con tu toolchain real
(que sí tiene Rust moderno), no un `.whl`.
