import { useState, useEffect, useRef, useCallback } from 'react';
import { Bell, Loader2 } from 'lucide-react';
import { Button } from '@/components/ui/button';

export default function ReminderBell({ token, activeTab, onOpenDrawer, onNewReminders }) {
  const [reminders, setReminders] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(false);
  const prevIdsRef = useRef(new Set());
  const intervalRef = useRef(null);
  const mountedRef = useRef(true);

  const fetchReminders = useCallback(async (silent = false) => {
    if (!token) return;
    if (!silent) setLoading(true);
    setError(false);
    try {
      const res = await fetch(`${import.meta.env.VITE_API_URL || ''}/v1/reminders`, {
        headers: { Authorization: `Bearer ${token}` },
      });
      if (!res.ok) throw new Error('API error');
      const data = await res.json();
      if (!mountedRef.current) return;

      const unread = data.unread || [];
      const read = data.read || [];
      const allReminders = [...unread, ...read];
      setReminders(allReminders);
      setLoading(false);

      // Check for new unacknowledged reminders (IDs not seen before)
      const currentIds = new Set(unread.map(r => r.id));
      const prevIds = prevIdsRef.current;
      if (prevIds.size > 0) {
        const newItems = unread.filter(r => !prevIds.has(r.id));
        if (newItems.length > 0 && onNewReminders) {
          onNewReminders(newItems);
        }
      }
      prevIdsRef.current = currentIds;
    } catch (err) {
      if (!mountedRef.current) return;
      setError(true);
      setLoading(false);
    }
  }, [token, onNewReminders]);

  // Initial fetch on mount
  useEffect(() => {
    mountedRef.current = true;
    if (token) {
      fetchReminders();
    }
    prevIdsRef.current = new Set();
    return () => {
      mountedRef.current = false;
    };
  }, [token, fetchReminders]);

  // Polling every 120s
  useEffect(() => {
    if (!token) return;
    intervalRef.current = setInterval(() => {
      fetchReminders(true);
    }, 120000);
    return () => {
      if (intervalRef.current) {
        clearInterval(intervalRef.current);
        intervalRef.current = null;
      }
    };
  }, [token, fetchReminders]);

  // visibilitychange + window focus re-fetch
  useEffect(() => {
    const handleVisibility = () => {
      if (document.visibilityState === 'visible') {
        fetchReminders(true);
      }
    };
    const handleFocus = () => {
      fetchReminders(true);
    };
    document.addEventListener('visibilitychange', handleVisibility);
    window.addEventListener('focus', handleFocus);
    return () => {
      document.removeEventListener('visibilitychange', handleVisibility);
      window.removeEventListener('focus', handleFocus);
    };
  }, [fetchReminders]);

  // Re-fetch on tab switch
  const prevTabRef = useRef(activeTab);
  useEffect(() => {
    if (prevTabRef.current !== activeTab) {
      prevTabRef.current = activeTab;
      fetchReminders(true);
    }
  }, [activeTab, fetchReminders]);

  const unacknowledged = reminders.filter(r => !r.acknowledged);
  const count = unacknowledged.length;

  // Error state: return null to hide the bell gracefully
  if (error) return null;

  return (
    <Button
      variant="ghost"
      size="icon"
      onClick={() => onOpenDrawer({ reminders, loading, error, onRefresh: () => fetchReminders() })}
      className="relative shrink-0"
      title="提醒"
    >
      {loading ? (
        <Loader2 size={18} className="animate-spin text-gray-400" />
      ) : (
        <Bell size={18} className="text-foreground" />
      )}
      {!loading && count > 0 && (
        <span className="absolute -top-0.5 -right-0.5 inline-flex items-center justify-center w-4 h-4 text-[10px] font-bold text-white bg-red-500 rounded-full">
          {count > 99 ? '99+' : count}
        </span>
      )}
    </Button>
  );
}
