//
// Created by yuhang on 2025/10/26.
//

#ifndef TIANYAN_TIANYANCORE_H
#define TIANYAN_TIANYANCORE_H
#include "database_backend.h"
#include <chrono>
#include <optional>
#include <unordered_map>
#include <vector>

using namespace std;
using TimePoint = std::chrono::steady_clock::time_point;

class IDatabaseBackend;

class TianyanCore {
public:
    explicit TianyanCore(IDatabaseBackend& db);
    // Directorios y rutas de archivos
    static constexpr std::string_view dataPath = "plugins/tianyan_data";
    static inline const string language_path = "plugins/tianyan_data/language/";
    static inline const string dbPath = "plugins/tianyan_data/ty_data.db";
    static inline const string config_path = "plugins/tianyan_data/config.json";
    static inline const string ban_id_path = "plugins/tianyan_data/ban-id.json";
    static inline string language_file = language_path + "en_US";
    // Variables de configuración
    static inline int max_message_in_10s;
    static inline int max_command_in_10s;
    static inline vector<string> no_log_mobs;
    static inline vector<string> no_log_blocks;
    static inline bool enable_web_ui = false;
    // Almacena la última marca de tiempo de activación de cada jugador
    static inline std::unordered_map<string, TimePoint> lastTriggerTime;
    // Caché global: lista de marcas de tiempo de mensajes por jugador (solo se conservan los últimos 10 segundos)
    static inline std::unordered_map<string, std::vector<TimePoint>> playerMessageTimes;
    // Caché global: lista de marcas de tiempo de comandos por jugador (solo se conservan los últimos 10 segundos)
    static inline std::unordered_map<string, std::vector<TimePoint>> playerCommandTimes;
    // Caché de estado de reversión - almacena los UUID de registro que deben marcarse como "reverted"
    static inline vector<pair<string, string>> revertStatusCache;

    // Estructura de datos de un registro
    struct LogData {
        string uuid;
        string id;
        string name;
        double pos_x = -1.0;
        double pos_y = -320.0;
        double pos_z = -1.0;
        string world;
        string obj_id;
        string obj_name;
        long long time = 0;
        string type;
        string data;
        string status;
    };

    // Datos de jugador baneado por ID de dispositivo
    struct BanIDPlayer {
        string player_name;
        string device_id;
        optional<string> reason;
        string time;
    };

    // Estructura para calcular la densidad de entidades
    struct DensityResult {
        std::optional<std::string> dim;
        std::optional<double> mid_x, mid_y, mid_z;
        std::optional<int> count;
        std::optional<std::string> entity_type;
        std::optional<std::string> entity_pos;
        std::optional<double> entity_pos_x, entity_pos_y, entity_pos_z;
    };


    // Convierte una marca de tiempo Unix en formato string a long long
    static long long stringToTimestamp(const std::string& timestampStr) ;

    // Convierte una marca de tiempo a formato legible para humanos
    static std::string timestampToString(long long timestamp);

    // Registra un evento
    [[nodiscard]] int recordLog(const LogData& logData) const;

    // Registra varios eventos en lote
    [[nodiscard]] int recordLogs(const std::vector<LogData>& logDatas) const;

    // Busca registros
    [[nodiscard]] vector<LogData> searchLog(const pair<string,double>& key, atomic<bool>* cancel = nullptr) const;

    // Busca registros并在指定世界和坐标范围内筛选
    [[nodiscard]] vector<LogData> searchLog(const pair<string,double>& key, double x, double y, double z, double r, const string& world, atomic<bool>* cancel = nullptr) const;

    // Registra que un jugador envió un mensaje (limpia automáticamente los registros expirados)
    static int recordPlayerSendMSG(const string& player_name);

    // Comprueba si el jugador superó el límite de mensajes en 10 segundos
    static bool checkPlayerSendMSG(const string& player_name);

    // Registra que un jugador envió un mensaje (limpia automáticamente los registros expirados)
    static int recordPlayerSendCMD(const string& player_name);

    // Comprueba si el jugador superó el límite de mensajes en 10 segundos
    static bool checkPlayerSendCMD(const string& player_name);
private:
    IDatabaseBackend& db_backend_;
};


#endif //TIANYAN_TIANYANCORE_H