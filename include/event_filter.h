//
// Sistema centralizado de filtros de eventos.
//
// Objetivo: decidir, con una sola consulta O(1) y ANTES de construir
// cualquier LogData, si un mob o un bloque debe ser ignorado por completo.
// Esto evita lógica duplicada repartida en event_listener.cpp y reduce el
// consumo de CPU al no crear registros que luego serían descartados.
//
#ifndef TIANYAN_EVENT_FILTER_H
#define TIANYAN_EVENT_FILTER_H

#include <string>
#include <unordered_set>
#include <vector>

class EventFilter {
public:
    // Reconstruye los conjuntos internos a partir de la configuración
    // (no_log_mobs / no_log_blocks). Debe llamarse cada vez que la
    // configuración se carga o se recarga.
    static void init(const std::vector<std::string>& no_log_mobs,
                      const std::vector<std::string>& no_log_blocks);

    // true si el tipo de entidad debe ignorarse SIEMPRE, sin importar
    // NameTag, CustomName, Variant ni ningún otro metadato de la entidad.
    static bool isMobIgnored(const std::string& entity_type);

    // true si el tipo de bloque debe ignorarse. Acepta tanto
    // "minecraft:stone" como "stone" y no distingue mayúsculas/minúsculas.
    static bool isBlockIgnored(const std::string& block_type);

    // Normaliza un identificador de bloque/entidad: minúsculas y agrega
    // el prefijo "minecraft:" si falta.
    static std::string normalize(const std::string& id);

private:
    static inline std::unordered_set<std::string> no_log_mobs_set_;
    static inline std::unordered_set<std::string> no_log_blocks_set_;
};

#endif //TIANYAN_EVENT_FILTER_H
