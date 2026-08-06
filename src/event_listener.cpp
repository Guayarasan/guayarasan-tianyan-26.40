//
// Created by yuhang on 2025/12/2.
//
// ReSharper disable CppMemberFunctionMayBeConst
#include "event_listener.h"
#include "tianyan_protect.h"
#include <tianyan_plugin.h>
#include <translate.hpp>
#include "database_util.h"
#include "event_filter.h"
#include <format>

EventListener::EventListener(TianyanPlugin* tianyan, translate* tran)
    :plugin_(*tianyan), tran_(tran)
{}


void EventListener::initOnlinePlayers()
{
    online_players_.clear();
    for (const auto* p : plugin_.getServer().getOnlinePlayers()) {
        online_players_.insert(p);
    }
}

// Comprueba si se permite disparar el evento
bool EventListener::canTriggerEvent(const string& playername) {
    const auto now = std::chrono::steady_clock::now();

    // Buscar la última marca de tiempo de activación del jugador
    if (TianyanCore::lastTriggerTime.contains(playername)) {
        const auto lastTime = TianyanCore::lastTriggerTime[playername];

        // Si la diferencia de tiempo es menor a 0.1s, no se permite disparar
        if (const auto elapsedTime = std::chrono::duration<double>(now - lastTime).count(); elapsedTime < 0.1) {
            return false;
        }
    }

    // Actualizar la última marca de tiempo del jugador a la actual
    TianyanCore::lastTriggerTime[playername] = now;
    return true;
}

void EventListener::onBlockBreak(const endstone::BlockBreakEvent& event){
    // Filtro centralizado: bloques en no_log_blocks nunca se registran
    if (EventFilter::isBlockIgnored(event.getBlock().getType())) {
        return;
    }
    TianyanCore::LogData logData;
    logData.uuid = db_util::generate_uuid_v4(); // Generar UUID
    logData.id = event.getPlayer().getType();
    logData.name = event.getPlayer().getName();
    logData.pos_x = event.getBlock().getX();
    logData.pos_y = event.getBlock().getY();
    logData.pos_z = event.getBlock().getZ();
    logData.world = event.getBlock().getLocation().getDimension().getName();
    logData.obj_id = event.getBlock().getType();
    logData.time = std::time(nullptr);
    logData.type = "block_break";
    if (event.isCancelled()) {
        logData.status = "canceled";
    }
    const auto block_data = event.getBlock().getData();
    auto block_states = block_data->getBlockStates();
    logData.data = std::format("{}", block_states);
    {
        std::lock_guard lock(cacheMutex);
        logDataCache.push_back(logData);
    }
}

void EventListener::onBlockPlace(const endstone::BlockPlaceEvent& event){
    // Filtro centralizado: bloques en no_log_blocks nunca se registran
    if (EventFilter::isBlockIgnored(event.getBlockPlacedState().getType())) {
        return;
    }
    TianyanCore::LogData logData;
    logData.uuid = db_util::generate_uuid_v4(); // Generar UUID
    logData.id = event.getPlayer().getType();
    logData.name = event.getPlayer().getName();
    logData.pos_x = event.getBlockPlacedState().getX();
    logData.pos_y = event.getBlockPlacedState().getY();
    logData.pos_z = event.getBlockPlacedState().getZ();
    logData.world = event.getBlockPlacedState().getLocation().getDimension().getName();
    logData.obj_id = event.getBlockPlacedState().getType();
    logData.time = std::time(nullptr);
    logData.type = "block_place";
    if (event.isCancelled()) {
        logData.status = "canceled";
    }
    const auto block_data = event.getBlockPlacedState().getData();
    auto block_states = block_data->getBlockStates();
    logData.data = std::format("{}", block_states);
    {
        std::lock_guard lock(cacheMutex);
        logDataCache.push_back(logData);
    }
}

void EventListener::onActorDamage(const endstone::ActorDamageEvent& event){
    // Mobs comunes sin nombre: no requieren atención especial
    // Se ignora SIEMPRE si el tipo está en no_log_mobs, sin importar NameTag/CustomName/metadata
    if (EventFilter::isMobIgnored(event.getActor().getType())) {
        return;
    }
    TianyanCore::LogData logData;
    logData.uuid = db_util::generate_uuid_v4(); // Generar UUID

    // La entidad causó daño
    if (event.getDamageSource().getActor()) {
        logData.id = event.getDamageSource().getActor()->getType();
        logData.name = event.getDamageSource().getActor()->getName();
        logData.type = "entity_damage";
    }
    // Resto de tipos de daño
    else {
        logData.id = event.getDamageSource().getType();
        logData.type = "damage";
    }
    logData.pos_x = event.getActor().getLocation().getX();
    logData.pos_y = event.getActor().getLocation().getY();
    logData.pos_z = event.getActor().getLocation().getZ();
    logData.world = event.getActor().getLocation().getDimension().getName();
    logData.obj_id = event.getActor().getType();
    logData.obj_name = event.getActor().getName();
    logData.time = std::time(nullptr);
    if (event.isCancelled()) {
        logData.status = "canceled";
    }
    auto damage = event.getDamage();
    logData.data = fmt::format("{}", damage);
    {
        std::lock_guard lock(cacheMutex);
        logDataCache.push_back(logData);
    }
}

void EventListener::onPlayerRightClickBlock(const endstone::PlayerInteractEvent& event) {
    TianyanCore::LogData logData;
    if (!event.getBlock()) {
        return;
    }
    // Filtro centralizado: bloques en no_log_blocks nunca se registran,
    // ni siquiera como interacción.
    if (EventFilter::isBlockIgnored(event.getBlock()->getType())) {
        return;
    }
    // Registrar la interacción con objetos específicos
    bool danger_item = false;
    if (event.hasItem())
    {
        static constexpr std::array<std::string_view, 4> dangerKeywords = {
            "end_crystal", "flint_and_steel", "fire_charge", "bucket"
        };
        const auto item_id = event.getItem()->getType().getId().getKey();

        auto containsKeyword = [&item_id](const std::string_view kw) {
            return item_id.find(kw) != std::string::npos;
        };

        if (ranges::any_of(dangerKeywords, containsKeyword)) {
            danger_item = true;
        }
    }
    // Contenedores: deben registrarse siempre que se abran, igual que un
    // cofre, incluso si en algún caso sus block states llegaran vacíos
    // (por ejemplo, Shulker Box de cualquier color). Endstone 0.11.5 no
    // expone un evento dedicado de apertura de inventario, por lo que este
    // es el único punto de la API donde se puede detectar la apertura.
    static constexpr std::array<std::string_view, 16> containerKeywords = {
        "chest", "barrel", "shulker_box", "dispenser", "dropper", "hopper",
        "furnace", "smoker", "brewing_stand", "lectern", "beacon",
        "decorated_pot", "campfire", "lodestone", "respawn_anchor", "bell"
    };
    const auto block_id = event.getBlock()->getType();
    auto containsContainerKeyword = [&block_id](const std::string_view kw) {
        return block_id.find(kw) != std::string::npos;
    };
    const bool is_container = ranges::any_of(containerKeywords, containsContainerKeyword);

    if (event.getBlock()->getData()->getBlockStates().empty() && !danger_item && !is_container)
    {
        return;
    }

    if (!canTriggerEvent(event.getPlayer().getName())) {
        return;
    }
    logData.uuid = db_util::generate_uuid_v4(); // Generar UUID
    logData.id = event.getPlayer().getType();
    logData.name = event.getPlayer().getName();
    logData.pos_x = event.getBlock()->getX();
    logData.pos_y = event.getBlock()->getY();
    logData.pos_z = event.getBlock()->getZ();
    logData.world = event.getPlayer().getLocation().getDimension().getName();
    logData.obj_id = event.getBlock()->getType();
    logData.time = std::time(nullptr);
    logData.type = "player_right_click_block";
    if (event.isCancelled()) {
        logData.status = "canceled";
    }
    string hand_item;
    if (event.hasItem()) {
        hand_item = event.getItem()->getType().getId();
    } else {
        hand_item = "hand";
    }
    const auto block_data = event.getBlock()->getData();
    auto block_states = block_data->getBlockStates();
    logData.data = std::format("{},{}", hand_item, block_states);
    {
        std::lock_guard lock(cacheMutex);
        logDataCache.push_back(logData);
    }
}

void EventListener::onPlayerRightClickActor(const endstone::PlayerInteractActorEvent& event){
    // Mobs comunes sin nombre: no requieren atención especial
    // Se ignora SIEMPRE si el tipo está en no_log_mobs, sin importar NameTag/CustomName/metadata
    if (EventFilter::isMobIgnored(event.getActor().getType())) {
        return;
    }
    TianyanCore::LogData logData;
    logData.uuid = db_util::generate_uuid_v4(); // Generar UUID
    logData.id = event.getPlayer().getType();
    logData.name = event.getPlayer().getName();
    logData.pos_x = event.getActor().getLocation().getX();
    logData.pos_y = event.getActor().getLocation().getY();
    logData.pos_z = event.getActor().getLocation().getZ();
    logData.world = event.getActor().getLocation().getDimension().getName();
    logData.obj_id = event.getActor().getType();
    logData.obj_name = event.getActor().getName();
    logData.time = std::time(nullptr);
    logData.type = "player_right_click_entity";
    if (event.isCancelled()) {
        logData.status = "canceled";
    }
    string hand_item;
    if (event.getPlayer().getInventory().getItemInMainHand()) {
        hand_item = event.getPlayer().getInventory().getItemInMainHand()->getType().getId();
    } else {
        hand_item = "hand";
    }
    logData.data = fmt::format("{}", hand_item);
    {
        std::lock_guard lock(cacheMutex);
        logDataCache.push_back(logData);
    }
}

void EventListener::onActorBomb(const endstone::ActorExplodeEvent& event) {
    TianyanCore::LogData logData;
    logData.uuid = db_util::generate_uuid_v4(); // Generar UUID
    logData.id = event.getActor().getType();
    logData.name = event.getActor().getName();
    logData.pos_x = event.getLocation().getX();
    logData.pos_y = event.getLocation().getY();
    logData.pos_z = event.getLocation().getZ();
    logData.world = event.getLocation().getDimension().getName();
    if (!event.getBlockList().empty()) {
        logData.obj_name = "Block";
    }
    logData.time = std::time(nullptr);
    logData.type = "entity_bomb";
    auto block_num = event.getBlockList().size();
    if (event.isCancelled()) {
        logData.status = "canceled";
        {
            std::lock_guard lock(cacheMutex);
            logDataCache.push_back(logData);
        }
    } else {
        logData.data = fmt::format("{}", block_num);
        {
            std::lock_guard lock(cacheMutex);
            logDataCache.push_back(logData);
        }
        for (const auto& block : event.getBlockList()) {
            // Tipo de bloque
            TianyanCore::LogData bomb_data;
            bomb_data.uuid = db_util::generate_uuid_v4(); // Generar UUID
            bomb_data.id = event.getActor().getType();
            bomb_data.name = event.getActor().getName();
            bomb_data.pos_x = block->getX();
            bomb_data.pos_y = block->getY();
            bomb_data.pos_z = block->getZ();
            bomb_data.world = block->getLocation().getDimension().getName();
            bomb_data.obj_id = block->getType();
            bomb_data.time = std::time(nullptr);
            bomb_data.type = "block_break_bomb";
            bomb_data.data = std::format("{}", block->getData()->getBlockStates());
            {
                std::lock_guard lock(cacheMutex);
                logDataCache.push_back(bomb_data);
            }
        }
    }
}

void EventListener::onBlockBomb(const endstone::BlockExplodeEvent& event)
{
    TianyanCore::LogData logData;
    logData.uuid = db_util::generate_uuid_v4();
    logData.id = event.getBlock().getType();
    logData.pos_x = event.getBlock().getX();
    logData.pos_y = event.getBlock().getY();
    logData.pos_z = event.getBlock().getZ();
    logData.world = event.getBlock().getLocation().getDimension().getName();
    if (!event.getBlockList().empty()) {
        logData.obj_name = "Block";
    }
    logData.time = std::time(nullptr);
    logData.type = "block_bomb";
    auto block_num = event.getBlockList().size();
    if (event.isCancelled()) {
        logData.status = "canceled";
        {
            std::lock_guard lock(cacheMutex);
            logDataCache.push_back(logData);
        }
    } else {
        logData.data = fmt::format("{}", block_num);
        {
            std::lock_guard lock(cacheMutex);
            logDataCache.push_back(logData);
        }
        for (const auto& block : event.getBlockList()) {
            TianyanCore::LogData bomb_data;
            if (block->getType() == "minecraft:air") {continue;}
            bomb_data.uuid = db_util::generate_uuid_v4();
            bomb_data.id = event.getBlock().getType();
            bomb_data.pos_x = block->getX();
            bomb_data.pos_y = block->getY();
            bomb_data.pos_z = block->getZ();
            bomb_data.world = block->getLocation().getDimension().getName();
            bomb_data.obj_id = block->getType();
            bomb_data.time = std::time(nullptr);
            bomb_data.type = "block_break_bomb";
            bomb_data.data = std::format("{}", block->getData()->getBlockStates());
            {
                std::lock_guard lock(cacheMutex);
                logDataCache.push_back(bomb_data);
            }
        }
    }
}

void EventListener::onPistonExtend(const endstone::BlockPistonExtendEvent&event) {
    // Los pistones generan miles de eventos inútiles en granjas automáticas.
    // Por diseño, este evento nunca construye ni inserta un registro en la
    // base de datos. Se mantiene el método (y su registro en onEnable) por
    // compatibilidad con la API de Endstone, pero es intencionalmente un no-op.
    (void)event;
}

void EventListener::onPistonRetract(const endstone::BlockPistonRetractEvent&event) {
    // Ver onPistonExtend: nunca se registra, por diseño.
    (void)event;
}

void EventListener::onActorDie(const endstone::ActorDeathEvent&event) {
    // Mobs comunes sin nombre: no requieren atención especial
    // Se ignora SIEMPRE si el tipo está en no_log_mobs, sin importar NameTag/CustomName/metadata
    if (EventFilter::isMobIgnored(event.getActor().getType())) {
        return;
    }
    TianyanCore::LogData logData;
    logData.uuid = db_util::generate_uuid_v4(); // Generar UUID
    logData.pos_x = event.getActor().getLocation().getX();
    logData.pos_y = event.getActor().getLocation().getY();
    logData.pos_z = event.getActor().getLocation().getZ();
    logData.world = event.getActor().getLocation().getDimension().getName();
    logData.obj_id = event.getActor().getType();
    logData.obj_name = event.getActor().getName();
    logData.time = std::time(nullptr);
    logData.type = "entity_die";
    {
        std::lock_guard lock(cacheMutex);
        logDataCache.push_back(logData);
    }
}

void EventListener::onPlayerDie(const endstone::PlayerDeathEvent&event) {
    TianyanCore::LogData logData;
    logData.uuid = db_util::generate_uuid_v4(); // Generar UUID
    logData.pos_x = event.getActor().getLocation().getX();
    logData.pos_y = event.getActor().getLocation().getY();
    logData.pos_z = event.getActor().getLocation().getZ();
    logData.world = event.getActor().getLocation().getDimension().getName();
    logData.obj_id = event.getActor().getType();
    logData.obj_name = event.getActor().getName();
    logData.time = std::time(nullptr);
    logData.type = "entity_die";
    {
        std::lock_guard lock(cacheMutex);
        logDataCache.push_back(logData);
    }
}

void EventListener::onPlayerPickup(const endstone::PlayerPickupItemEvent&event) {
    TianyanCore::LogData logData;
    const endstone::Player& player = event.getPlayer();
    if (!online_players_.contains(&player)) {
        return;
    }
    logData.uuid = db_util::generate_uuid_v4();
    logData.id = player.getType();
    logData.name = player.getName();
    logData.pos_x = player.getLocation().getX();
    logData.pos_y = player.getLocation().getY();
    logData.pos_z = player.getLocation().getZ();
    logData.world = player.getLocation().getDimension().getName();
    logData.obj_id = event.getItem().getItemStack().getType().getId();
    logData.obj_name = event.getItem().getName();
    logData.time = std::time(nullptr);
    logData.type = "player_pickup_item";
    if (event.isCancelled()) {
        logData.status = "canceled";
    }
    {
        std::lock_guard lock(cacheMutex);
        logDataCache.push_back(logData);
    }
}

void EventListener::onPlayerDropItem(const endstone::PlayerDropItemEvent& event) {
    TianyanCore::LogData logData;

    const endstone::Player& player = event.getPlayer();
    if (!online_players_.contains(&player)) {
        return;
    }
    logData.uuid = db_util::generate_uuid_v4();
    logData.id = player.getType();
    logData.name = player.getName();
    logData.pos_x = player.getLocation().getX();
    logData.pos_y = player.getLocation().getY();
    logData.pos_z = player.getLocation().getZ();
    logData.world = player.getLocation().getDimension().getName();
    logData.obj_id = event.getItem().getType().getId();
    logData.time = std::time(nullptr);
    logData.type = "player_drop_item";
    if (event.isCancelled()) {
        logData.status = "canceled";
    }
    {
        std::lock_guard lock(cacheMutex);
        logDataCache.push_back(logData);
    }
}

// Propagación natural de líquidos (agua/lava fluyendo entre bloques).
// Nunca se registra: genera un volumen enorme de eventos sin valor de
// auditoría. La colocación/recolección de líquidos CON CUBETA por parte
// de un jugador se sigue registrando normalmente como block_place/block_break,
// ya que esos eventos son disparados por el jugador y no por este evento.
void EventListener::onBlockFromTo(const endstone::BlockFromToEvent& event) {
    (void)event;
}

// Entidad "no viva" destruida: minecarts (incl. con cofre/tolva/TNT), botes,
// Item Frame, Glow Item Frame y Armor Stand. ActorDeathEvent solo se dispara
// para Mob, así que estas entidades pueden desaparecer sin dejar rastro si
// no se escucha también ActorRemoveEvent. Se filtra estrictamente a estos
// tipos porque ActorRemoveEvent se dispara para CUALQUIER entidad que
// desaparece (drops de items, orbes de experiencia, proyectiles...), y no
// queremos ese ruido.
void EventListener::onActorRemove(const endstone::ActorRemoveEvent& event) {
    static constexpr std::array<std::string_view, 4> trackedKeywords = {
        "minecart", "boat", "item_frame", "armor_stand"
    };
    const auto type = event.getActor().getType();
    auto containsKeyword = [&type](const std::string_view kw) {
        return type.find(kw) != std::string::npos;
    };
    if (!ranges::any_of(trackedKeywords, containsKeyword)) {
        return;
    }
    TianyanCore::LogData logData;
    logData.uuid = db_util::generate_uuid_v4();
    logData.id = event.getActor().getType();
    logData.name = event.getActor().getName();
    logData.pos_x = event.getActor().getLocation().getX();
    logData.pos_y = event.getActor().getLocation().getY();
    logData.pos_z = event.getActor().getLocation().getZ();
    logData.world = event.getActor().getLocation().getDimension().getName();
    logData.obj_id = event.getActor().getType();
    logData.time = std::time(nullptr);
    logData.type = "vehicle_destroy";
    {
        std::lock_guard lock(cacheMutex);
        logDataCache.push_back(logData);
    }
}

// Evento: jugador se une
void EventListener::onPlayerJoin(const endstone::PlayerJoinEvent &event) {
    if (!event.getPlayer().asPlayer()) return;
    online_players_.insert(&event.getPlayer());

    // Cachear el mapeo nombre de jugador → UUID
    OfflineInventoryReader::updatePlayerCache(
        event.getPlayer().getName(),
        event.getPlayer().getUniqueId().str()
    );

    std::ostringstream out;
    out << endstone::ColorFormat::Yellow << tran_->getLocal("Player") << " " << event.getPlayer().getName() << " " << tran_->getLocal("joined server!")
    << " " <<tran_->getLocal("Device OS: ")<< event.getPlayer().getDeviceOS() << " " << tran_->getLocal("Device ID: ") << event.getPlayer().getDeviceId();
    plugin_.getServer().getLogger().info(out.str());
}

// Evento: jugador se desconecta
void EventListener::onPlayerLeave(const endstone::PlayerQuitEvent& event)
{
    online_players_.erase(&event.getPlayer());
}


// Detección de spam de mensajes
void EventListener::onPlayerSendMSG(const endstone::PlayerChatEvent &event) {
    TianyanCore::recordPlayerSendMSG(event.getPlayer().getName());
    if (TianyanCore::checkPlayerSendMSG(event.getPlayer().getName())) {
        string reason = tran_->getLocal("Too many messages sent in a short time");
        plugin_.getServer().getBanList().addBan(event.getPlayer().getName(),reason, std::chrono::hours(24), "Tianyan Plugin");
        event.getPlayer().kick(reason);
        plugin_.getServer().broadcastMessage(endstone::ColorFormat::Yellow + tran_->getLocal("Player") + ": " + event.getPlayer().getName() + " " + tran_->getLocal("has been banned for sending too many messages in a short time"));
    }
}

// Detección de spam de comandos
void EventListener::onPlayerSendCMD(const endstone::PlayerChatEvent &event) {
    TianyanCore::recordPlayerSendCMD(event.getPlayer().getName());
    if (TianyanCore::checkPlayerSendCMD(event.getPlayer().getName())) {
        string reason = tran_->getLocal("Too many commands sent in a short time");
        plugin_.getServer().getBanList().addBan(event.getPlayer().getName(),reason, std::chrono::hours(24), "Tianyan Plugin");
        event.getPlayer().kick(reason);
        plugin_.getServer().broadcastMessage(endstone::ColorFormat::Yellow + tran_->getLocal("Player") + ": " + event.getPlayer().getName() + " " + tran_->getLocal("has been banned for sending too many commands in a short time"));
    }
}

// Rechazar la entrada de jugadores baneados
void EventListener::onPlayerTryJoin(const endstone::PlayerLoginEvent &event) {
    const auto player_name = event.getPlayer().getName();
    const auto device_id = event.getPlayer().getDeviceId();
    // Comprobar si el dispositivo del jugador ya está baneado
    if (const auto banData = TianyanProtect::getBannedPlayerByDeviceId(device_id);banData.has_value()) {
        const auto reason = banData.value().reason.value_or("");
        if (banData->player_name == "Null") {
            if (TianyanProtect::updatePlayerNameForDeviceId(banData.value().device_id,player_name)) {
                plugin_.getLogger().info(endstone::ColorFormat::Yellow+tran_->getLocal("Player")+": "+player_name + " " + tran_->getLocal("has been banned for using a banned device")+": " + banData.value().device_id);
            } else {
                plugin_.getLogger().error(tran_->getLocal("Unknow Error"));
            }
            event.getPlayer().kick(tran_->getLocal("Your device has been baned")+": "+reason);
        } else {
            event.getPlayer().kick(tran_->getLocal("Your device has been baned")+": "+reason);
            plugin_.getLogger().info(endstone::ColorFormat::Yellow+tran_->getLocal("Baned player: ")+player_name+" ("+device_id+") "+tran_->getLocal("try to join server"));
        }
    }
    // Comprobar por ID de dispositivo si se usó un dispositivo baneado
    else {
        if (TianyanProtect::isPlayerBanned(player_name)) {
            plugin_.getLogger().info(endstone::ColorFormat::Yellow+tran_->getLocal("Baned player: ")+player_name+" ("+device_id+") "+tran_->getLocal("try to join server"));
            string reason;
            for (const auto &baned_player : BanIDPlayers) {
                if (baned_player.player_name == player_name) {
                    reason = baned_player.reason.value_or("");
                    break;
                }
            }
            if (reason.empty()) {
                (void)plugin_.getServer().dispatchCommand(plugin_.getServer().getCommandSender(),"ban-id " + device_id);
            } else {
                (void)plugin_.getServer().dispatchCommand(plugin_.getServer().getCommandSender(),"ban-id " + device_id+ " \"" + reason +"\"");
            }
            event.getPlayer().kick(tran_->getLocal("Your device has been baned")+": "+reason);
        }
    }
}
