import { useEffect, useState } from 'react';
import { useParams, useNavigate, Link } from 'react-router-dom';
import {
  fetchSplitGroupDetail, fetchSplitExpenses, updateSplitGroupSettlementMode,
  addSplitGroupMember, removeSplitGroupMember, lookupSplitUser,
} from '../../../api/endpoints';
import { formatMoneyPrecise } from '../../../utils/money';
import { useAuth } from '../../../context/AuthContext';
import { Button, Banner, Spinner, EmptyState, Radio } from '../../../components/ui';
import './GroupDetailPage.css';

export default function GroupDetailPage() {
  const { id } = useParams();
  const navigate = useNavigate();
  const { user } = useAuth();
  const [group, setGroup] = useState(null);
  const [expenses, setExpenses] = useState(null);
  const [error, setError] = useState('');
  const [busy, setBusy] = useState(false);
  const [showAddMember, setShowAddMember] = useState(false);
  const [memberInput, setMemberInput] = useState('');
  const [memberError, setMemberError] = useState('');

  const load = async () => {
    const [groupRes, expensesRes] = await Promise.all([fetchSplitGroupDetail(id), fetchSplitExpenses(id)]);
    setGroup(groupRes.data);
    setExpenses(expensesRes.data);
  };

  useEffect(() => { load(); /* eslint-disable-next-line */ }, [id]);

  if (!group || !expenses) return <Spinner label="Loading group" />;

  const isCreator = group.created_by === user.id;

  const handleAddMember = async (e) => {
    e.preventDefault();
    const username = memberInput.trim();
    if (!username) return;
    setMemberError(''); setBusy(true);
    try {
      const { data } = await lookupSplitUser(username);
      if (!data.found) {
        setMemberError(`No user found with the username "${username}".`);
        return;
      }
      await addSplitGroupMember(id, data.id);
      setMemberInput(''); setShowAddMember(false);
      await load();
    } catch (err) {
      setMemberError(err.response?.data?.detail || err.response?.data?.user_id || 'Could not add member.');
    } finally {
      setBusy(false);
    }
  };

  const handleRemoveMember = async (userId, isSelf) => {
    if (!window.confirm(isSelf ? 'Leave this group?' : 'Remove this member from the group?')) return;
    setError(''); setBusy(true);
    try {
      await removeSplitGroupMember(id, userId);
      if (isSelf) { navigate('/splits'); return; }
      await load();
    } catch (err) {
      setError(err.response?.data?.detail || 'Could not remove member.');
    } finally {
      setBusy(false);
    }
  };

  const handleModeChange = async (mode) => {
    if (!isCreator || mode === group.settlement_mode) return;
    setError(''); setBusy(true);
    try {
      await updateSplitGroupSettlementMode(id, mode);
      await load();
    } catch (err) {
      setError(err.response?.data?.detail || 'Could not update settlement mode.');
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="group-detail">
      <p className="page-subtitle">{group.name}</p>
      {error && <Banner tone="warn">{error}</Banner>}

      <section className="group-detail__section">
        <div className="group-detail__section-head">
          <h2>Members</h2>
          <Button size="sm" variant="secondary" onClick={() => setShowAddMember((v) => !v)}>
            {showAddMember ? 'Cancel' : '+ Add member'}
          </Button>
        </div>

        {showAddMember && (
          <form onSubmit={handleAddMember} className="group-detail__add-member">
            <input
              className="ui-input" value={memberInput} onChange={(e) => setMemberInput(e.target.value)}
              placeholder="Enter a username" autoFocus
            />
            <Button type="submit" size="sm" disabled={busy || !memberInput.trim()}>Add</Button>
          </form>
        )}
        {memberError && <p className="ui-field__error" role="alert">{memberError}</p>}

        <ul className="group-detail__members">
          {group.members.map((m) => {
            const isSelf = m.user.id === user.id;
            const canRemove = isSelf || isCreator;
            return (
              <li key={m.id} className="group-detail__member-row">
                <span>
                  {m.user.username}{isSelf && ' (you)'}
                  {m.role === 'admin' && <span className="group-detail__admin-tag">Creator</span>}
                </span>
                {canRemove && m.role !== 'admin' && (
                  <button
                    type="button" className="group-detail__member-action" disabled={busy}
                    onClick={() => handleRemoveMember(m.user.id, isSelf)}
                  >
                    {isSelf ? 'Leave' : 'Remove'}
                  </button>
                )}
              </li>
            );
          })}
        </ul>
      </section>

      <section className="group-detail__section">
        <div className="group-detail__section-head">
          <h2>Expenses</h2>
        </div>
        {expenses.length === 0 ? (
          <EmptyState title="No expenses yet" message="Add the group's first shared expense." />
        ) : (
          <div className="group-detail__expenses">
            {expenses.map((exp) => (
              <div key={exp.id} className="group-detail__expense-row">
                <span className="group-detail__expense-desc">{exp.description}</span>
                <span className="group-detail__expense-amount">{formatMoneyPrecise(exp.amount)}</span>
              </div>
            ))}
          </div>
        )}
        <Link to={`/splits/${id}/expenses/new`}>
          <Button className="group-detail__add-expense-btn">+ Add Expense</Button>
        </Link>
      </section>

      <section className="group-detail__section">
        <h2>Settlement Mode</h2>
        <Radio
          name="mode" value="global" checked={group.settlement_mode === 'global'}
          onChange={() => handleModeChange('global')} disabled={!isCreator || busy}
          label="Fewest Payments" hint="Simplifies debts group-wide into the minimum number of transfers."
        />
        <Radio
          name="mode" value="pairwise" checked={group.settlement_mode === 'pairwise'}
          onChange={() => handleModeChange('pairwise')} disabled={!isCreator || busy}
          label="Detailed" hint="Keeps a direct balance between every pair of members."
        />
        {!isCreator && <p className="group-detail__mode-hint">Only the group creator can change this.</p>}
      </section>

      <Link to={`/splits/${id}/settlements`}>
        <Button size="lg" className="group-detail__settle-btn">Settle Up</Button>
      </Link>
    </div>
  );
}
