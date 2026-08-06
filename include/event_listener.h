//
// Created by yuhang on 2025/11/6.
//

// ReSharper disable CppMemberFunctionMayBeConst
#ifndef TIANYAN_EVENTLISTENER_H
#define TIANYAN_EVENTLISTENER_H
#include <endstone/endstone.hpp>

#include "translate.hpp"

class TianyanPlugin;
class translate;


class EventListener {
public:
    explicit EventListener(TianyanPlugin* tianyan, translate* tran);

    void initOnlinePlayers();

    // Comprueba si se permite disparar el evento (anti-spam)
    static bool canTriggerEvent(const std::string& playername);

    // Bloque destruido
    static void onBlockBreak(const endstone::BlockBreakEvent& event);

    // Bloque colocado
    static void onBlockPlace(const endstone::BlockPlaceEvent& event);

    // Entidad recibe daño
    static void onActorDamage(const endstone::ActorDamageEvent& event);

    // Jugador hace clic derecho en un bloque
    static void onPlayerRightClickBlock(const endstone::PlayerInteractEvent& event);

    // Jugador hace clic derecho en una entidad
    static void onPlayerRightClickActor(const endstone::PlayerInteractActorEvent& event);

    // Entidad explota
    static void onActorBomb(const endstone::ActorExplodeEvent& event);

    // Bloque explota
    static void onBlockBomb(const endstone::BlockExplodeEvent& event);

    // Pistón se extiende (no se registra, ver event_listener.cpp)
    static void onPistonExtend(const endstone::BlockPistonExtendEvent&event);

    // Pistón se retrae (no se registra, ver event_listener.cpp)
    static void onPistonRetract(const endstone::BlockPistonRetractEvent&event);

    //实体死了
    static void onActorDie(const endstone::ActorDeathEvent&event);

    // Vehículo destruido (minecart, minecart con cofre/embudo, bote, etc.)
    static void onActorRemove(const endstone::ActorRemoveEvent&event);

    //玩家死了
    static void onPlayerDie(const endstone::PlayerDeathEvent&event);

    // Flujo natural de líquidos (no se registra, ver event_listener.cpp)
    static void onBlockFromTo(const endstone::BlockFromToEvent& event);

    // Jugador recoge un objeto
    void onPlayerPickup(const endstone::PlayerPickupItemEvent&event);

    // Jugador suelta un objeto
    void onPlayerDropItem(const endstone::PlayerDropItemEvent& event);

    // Evento: jugador se une
    void onPlayerJoin(const endstone::PlayerJoinEvent &event);

    // Evento: jugador se desconecta
    void onPlayerLeave(const endstone::PlayerQuitEvent &event);

    // Detección de spam de mensajes
    void onPlayerSendMSG(const endstone::PlayerChatEvent &event);

    // Detección de spam de comandos
    void onPlayerSendCMD(const endstone::PlayerChatEvent &event);

    // Rechaza la entrada de jugadores baneados
    void onPlayerTryJoin(const endstone::PlayerLoginEvent &event);

private:
    endstone::Plugin &plugin_;
    translate* tran_;
    std::unordered_set<const endstone::Player*> online_players_;
};

#endif //TIANYAN_EVENTLISTENER_H
