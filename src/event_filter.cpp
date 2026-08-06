#include "event_filter.h"
#include <algorithm>
#include <cctype>

std::string EventFilter::normalize(const std::string& id) {
    std::string out = id;
    std::ranges::transform(out, out.begin(), [](const unsigned char c) { return std::tolower(c); });
    if (out.find(':') == std::string::npos) {
        out = "minecraft:" + out;
    }
    return out;
}

void EventFilter::init(const std::vector<std::string>& no_log_mobs, const std::vector<std::string>& no_log_blocks) {
    no_log_mobs_set_.clear();
    for (const auto& mob : no_log_mobs) {
        no_log_mobs_set_.insert(normalize(mob));
    }
    no_log_blocks_set_.clear();
    for (const auto& block : no_log_blocks) {
        no_log_blocks_set_.insert(normalize(block));
    }
}

bool EventFilter::isMobIgnored(const std::string& entity_type) {
    if (no_log_mobs_set_.empty()) return false;
    return no_log_mobs_set_.contains(normalize(entity_type));
}

bool EventFilter::isBlockIgnored(const std::string& block_type) {
    if (no_log_blocks_set_.empty()) return false;
    return no_log_blocks_set_.contains(normalize(block_type));
}
