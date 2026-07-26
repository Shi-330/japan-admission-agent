import { useState, useCallback } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { X, Check, Bell, Calendar, User, Loader2, RefreshCw, FileText, ChevronDown, ChevronRight, EyeOff } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { apiCall } from '@/lib/api';

const severityColors = {
  high: 'bg-urgency-high/10 border-l-4 border-urgency-high',
  medium: 'bg-urgency-medium/10 border-l-4 border-urgency-medium',
  low: 'bg-muted border-l-4 border-muted-foreground/30',
};

const severityIconColors = {
  high: 'text-urgency-high',
  medium: 'text-urgency-medium',
  low: 'text-muted-foreground',
};

function typeIcon(type) {
  switch (type) {
    case 'professor_no_reply':
      return <User size={14} />;
    case 'deadline_approaching':
    case 'deadline_expired':
      return <Calendar size={14} />;
    case 'profile_incomplete':
      return <User size={14} />;
    default:
      return <Bell size={14} />;
  }
}

const ACTION_CONFIG = {
  draft_outreach: { Icon: FileText, label: '拟套磁信' },
  goto_calendar: { Icon: Calendar, label: '去日历' },
  open_profile:   { Icon: User, label: '补全背景' },
};

export default function ReminderDrawer({
  open, onClose, reminders, loading, error,
  onRefresh, token, onAction, onNavigate
}) {
  const [ackLoading, setAckLoading] = useState(new Set());
  const [ackAllLoading, setAckAllLoading] = useState(false);

  const handleAck = useCallback(async (reminderId) => {
    setAckLoading(prev => new Set(prev).add(reminderId));
    try {
      await apiCall('/v1/reminders/ack', token, { method: 'POST', body: { id: reminderId } });
      onRefresh?.();
    } catch (err) {
      console.warn('Ack failed:', err);
    } finally {
      setAckLoading(prev => {
        const next = new Set(prev);
        next.delete(reminderId);
        return next;
      });
    }
  }, [token, onRefresh]);

  const handleAckAll = useCallback(async () => {
    setAckAllLoading(true);
    try {
      await apiCall('/v1/reminders/ack', token, { method: 'POST', body: { all: true } });
      onRefresh?.();
    } catch (err) {
      console.warn('Ack-all failed:', err);
    } finally {
      setAckAllLoading(false);
    }
  }, [token, onRefresh]);

  const handleActionClick = useCallback((reminder) => {
    if (onAction) {
      onAction(reminder);
    }
  }, [onAction]);

  const formatDays = (days) => {
    if (days < 0) return `已过期 ${Math.abs(days)} 天`;
    return `${days} 天后`;
  };

  const [showRead, setShowRead] = useState(false);

  const unacknowledged = (reminders || []).filter(r => !r.acknowledged);
  const acknowledged = (reminders || []).filter(r => r.acknowledged);

  return (
    <AnimatePresence>
      {open && (
        <>
          {/* Overlay */}
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            transition={{ duration: 0.2 }}
            className="fixed inset-0 bg-black/30 z-40"
            onClick={onClose}
          />

          {/* Drawer */}
          <motion.div
            initial={{ x: '100%' }}
            animate={{ x: 0 }}
            exit={{ x: '100%' }}
            transition={{ duration: 0.2, ease: 'easeOut' }}
            className="fixed right-0 top-0 h-full w-full max-w-sm bg-background shadow-xl z-50 flex flex-col"
          >
            {/* Header */}
            <div className="flex items-center justify-between px-4 py-3 border-b border-border shrink-0">
              <h3 className="text-base font-semibold">提醒</h3>
              <div className="flex items-center gap-2">
                {unacknowledged.length > 0 && (
                  <Button
                    variant="ghost"
                    size="sm"
                    onClick={handleAckAll}
                    disabled={ackAllLoading}
                    className="text-xs text-muted-foreground hover:text-foreground"
                  >
                    {ackAllLoading ? <Loader2 size={12} className="animate-spin mr-1" /> : null}
                    全部已读
                  </Button>
                )}
                <Button variant="ghost" size="icon" onClick={onClose} className="h-7 w-7">
                  <X size={16} />
                </Button>
              </div>
            </div>

            {/* Content */}
            <div className="flex-1 overflow-y-auto p-4">
              {loading ? (
                <div className="flex items-center justify-center h-32">
                  <Loader2 size={20} className="animate-spin text-muted-foreground" />
                </div>
              ) : error ? (
                <div className="flex flex-col items-center justify-center h-32 text-muted-foreground">
                  <p className="text-sm mb-2">加载失败，请稍后再试</p>
                  <Button variant="outline" size="sm" onClick={onRefresh} className="text-xs">
                    <RefreshCw size={12} className="mr-1" /> 重试
                  </Button>
                </div>
              ) : unacknowledged.length === 0 && acknowledged.length === 0 ? (
                <div className="flex items-center justify-center h-32">
                  <p className="text-sm text-muted-foreground">暂无提醒</p>
                </div>
              ) : (
                <div className="space-y-3">
                  {/* Unread section */}
                  {unacknowledged.length > 0 && (
                    <div className="space-y-2">
                      {unacknowledged.map((reminder) => {
                        const isAckLoading = ackLoading.has(reminder.id);
                        return (
                          <div
                            key={reminder.id}
                            className={`${severityColors[reminder.severity] || 'bg-white border'} rounded p-3`}
                          >
                            <div className="flex items-start gap-2">
                              <span className={`mt-0.5 shrink-0 ${severityIconColors[reminder.severity] || 'text-gray-400'}`}>
                                {typeIcon(reminder.type)}
                              </span>
                              <div className="flex-1 min-w-0">
                                <p className="text-sm text-foreground mb-1">{reminder.message}</p>
                                <span className={`text-xs font-medium ${
                                  reminder.days < 0 ? 'text-urgency-high' :
                                  reminder.days <= 7 ? 'text-urgency-high' :
                                  reminder.days <= 14 ? 'text-urgency-medium' :
                                  'text-muted-foreground'
                                }`}>
                                  {formatDays(reminder.days)}
                                </span>
                              </div>
                            </div>

                            {/* Action button row */}
                            {reminder.action && ACTION_CONFIG[reminder.action.type] && (() => {
                              const cfg = ACTION_CONFIG[reminder.action.type];
                              const Icon = cfg.Icon;
                              return (
                                <div className="mt-2 ml-6 mb-1">
                                  <Button
                                    variant="default"
                                    size="sm"
                                    onClick={(e) => { e.stopPropagation(); handleActionClick(reminder); }}
                                    className="text-xs px-3 py-1 h-7 bg-primary text-primary-foreground hover:bg-indigo-700"
                                  >
                                    <Icon size={11} className="mr-1" />
                                    {cfg.label}
                                  </Button>
                                </div>
                              );
                            })()}

                            {/* Ack buttons */}
                            <div className="flex gap-1 mt-1 ml-6">
                              <Button
                                variant="ghost"
                                size="sm"
                                onClick={(e) => { e.stopPropagation(); handleAck(reminder.id); }}
                                disabled={isAckLoading}
                                className="text-xs text-muted-foreground hover:text-foreground h-7 px-2"
                              >
                                {isAckLoading ? <Loader2 size={10} className="animate-spin mr-1" /> : <Check size={10} className="mr-1" />}
                                标记已读
                              </Button>
                            </div>
                          </div>
                        );
                      })}
                    </div>
                  )}

                  {/* Read section (collapsible) */}
                  {acknowledged.length > 0 && (
                    <div>
                      <button
                        onClick={() => setShowRead(!showRead)}
                        className="flex items-center gap-1 text-xs text-muted-foreground hover:text-foreground transition-colors w-full py-1"
                      >
                        {showRead ? <ChevronDown size={12} /> : <ChevronRight size={12} />}
                        <EyeOff size={12} className="ml-0.5" />
                        <span>已读 ({acknowledged.length})</span>
                      </button>
                      {showRead && (
                        <div className="space-y-1.5 mt-1">
                          {acknowledged.map((reminder) => (
                            <div
                              key={reminder.id}
                              className="bg-gray-50 border border-gray-100 rounded p-2.5 opacity-60"
                            >
                              <div className="flex items-start gap-2">
                                <span className="mt-0.5 shrink-0 text-gray-400">
                                  {typeIcon(reminder.type)}
                                </span>
                                <div className="flex-1 min-w-0">
                                  <p className="text-xs text-gray-500 mb-0.5">{reminder.message}</p>
                                  <span className="text-[10px] text-gray-400">{formatDays(reminder.days)}</span>
                                </div>
                              </div>
                            </div>
                          ))}
                        </div>
                      )}
                    </div>
                  )}
                </div>
              )}
            </div>
          </motion.div>
        </>
      )}
    </AnimatePresence>
  );
}
