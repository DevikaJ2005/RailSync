import React from 'react';
import { View, Text, TouchableOpacity, StyleSheet } from 'react-native';
import { colors } from '../theme';

export default function TabStrip({ tabs, active, onSelect, badgeFor }) {
  return (
    <View style={styles.strip}>
      {tabs.map((tab) => {
        const isActive = active === tab.key;
        const badge = badgeFor?.(tab.key);
        return (
          <TouchableOpacity
            key={tab.key}
            style={[styles.tab, isActive && styles.tabActive]}
            onPress={() => onSelect(tab.key)}
          >
            <Text style={[styles.tabText, isActive && styles.tabTextActive]}>{tab.label}</Text>
            {badge != null && badge > 0 && (
              <View style={styles.badge}><Text style={styles.badgeText}>{badge}</Text></View>
            )}
          </TouchableOpacity>
        );
      })}
    </View>
  );
}

const styles = StyleSheet.create({
  strip: {
    flexDirection: 'row',
    borderBottomWidth: 1,
    borderBottomColor: colors.lineSteel,
  },
  tab: {
    flex: 1,
    paddingVertical: 12,
    alignItems: 'center',
    flexDirection: 'row',
    justifyContent: 'center',
    gap: 6,
    borderBottomWidth: 2,
    borderBottomColor: 'transparent',
  },
  tabActive: { borderBottomColor: colors.railBlue },
  tabText: {
    fontSize: 12,
    fontWeight: '600',
    color: colors.textMuted,
  },
  tabTextActive: { color: colors.textPrimary },
  badge: {
    backgroundColor: colors.signalRed,
    borderRadius: 8,
    minWidth: 18,
    paddingHorizontal: 5,
    paddingVertical: 1,
    alignItems: 'center',
  },
  badgeText: { color: '#fff', fontSize: 10, fontWeight: '700' },
});