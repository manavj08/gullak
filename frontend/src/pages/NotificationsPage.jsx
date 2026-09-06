import { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import {
  fetchNotifications, respondToInvite, respondToAdminTransfer,
} from '../api/endpoints';
import { Card, Button, Banner, EmptyState, Spinner } from '../components/ui';
import './NotificationsPage.css';

const TYPE_LABEL = {
  invite: 'Invite',
  admin_transfer: 'Admin request',
  reminder: 'Reminder',
  goal_underfunded: 'Goal update',
  member_joined: 'Member joined',
  member_left: 'Member left',
  admin_changed: 'Admin changed',
};

export default function NotificationsPage() {
  const [notifications, setNotifications] = useState(null);
  const [error, setError] = useState('');
  const [busyId, setBusyId] = useState(null);

  const load = async () => {
    const { data } = await fetchNotifications();
    setNotifications(data.results ?? data);
  };

  useEffect(() => { load(); }, []);

  const handleInviteResponse = async (notification, accept) => {
    setError('');
    setBusyId(notification.id);
    try {
      await respondToInvite(notification.related_invite, accept);
      await load();
    } catch (err) {
      setError(err.response?.data?.detail || 'Could not respond to invite.');
    } finally {
      setBusyId(null);
    }
  };

  const handleAdminTransferResponse = async (notification, accept) => {
    setError('');
    setBusyId(notification.id);
    try {
      await respondToAdminTransfer(notification.related_admin_transfer, accept);
      await load();
    } catch (err) {
      setError(err.response?.data?.detail || 'Could not respond to request.');
    } finally {
      setBusyId(null);
    }
  };

  if (notifications === null) return <Spinner label="Loading notifications" />;

  return (
    <div>
      {error && <Banner tone="warn">{error}</Banner>}

      {notifications.length === 0 ? (
        <EmptyState
          icon={<BellIcon />}
          title="No notifications yet"
          message="Invites, admin changes, and account activity will show up here."
        />
      ) : (
        <div className="notif-list">
          {notifications.map((n) => {
            const pending = n.actionable && n.status !== 'actioned';
            return (
              <Card key={n.id} className={`notif-item${n.status === 'unread' ? ' notif-item--unread' : ''}`}>
                <div className="notif-item__head">
                  <span className="notif-item__type">{TYPE_LABEL[n.type] || n.type}</span>
                  <span className="notif-item__time">{new Date(n.created_at).toLocaleString('en-IN', { dateStyle: 'medium', timeStyle: 'short' })}</span>
                </div>
                <p className="notif-item__title">{n.title}</p>
                {n.body && <p className="notif-item__body">{n.body}</p>}

                {pending && n.type === 'invite' && (
                  <div className="notif-item__actions">
                    <Button size="sm" variant="success" disabled={busyId === n.id} onClick={() => handleInviteResponse(n, true)}>
                      Accept
                    </Button>
                    <Button size="sm" variant="secondary" disabled={busyId === n.id} onClick={() => handleInviteResponse(n, false)}>
                      Decline
                    </Button>
                  </div>
                )}

                {pending && n.type === 'admin_transfer' && (
                  <div className="notif-item__actions">
                    <Button size="sm" variant="success" disabled={busyId === n.id} onClick={() => handleAdminTransferResponse(n, true)}>
                      Accept
                    </Button>
                    <Button size="sm" variant="secondary" disabled={busyId === n.id} onClick={() => handleAdminTransferResponse(n, false)}>
                      Decline
                    </Button>
                  </div>
                )}

                {n.type === 'goal_underfunded' && (
                  <Link to="/goals" className="notif-item__link">View goals →</Link>
                )}
                {(n.type === 'member_joined' || n.type === 'member_left' || n.type === 'admin_changed') && n.related_entity_id && (
                  <Link to={`/shared-accounts/${n.related_entity_id}`} className="notif-item__link">View account →</Link>
                )}
              </Card>
            );
          })}
        </div>
      )}
    </div>
  );
}

function BellIcon() {
  return <svg width="40" height="40" viewBox="0 0 24 24" fill="none"><path d="M6 9a6 6 0 0 1 12 0c0 4 1.5 5.5 1.5 5.5H4.5S6 13 6 9Z" stroke="currentColor" strokeWidth="1.6" strokeLinejoin="round"/><path d="M9.5 17a2.5 2.5 0 0 0 5 0" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round"/></svg>;
}
