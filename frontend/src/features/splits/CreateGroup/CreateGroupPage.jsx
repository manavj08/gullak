import { useState } from 'react';
import { useNavigate, Link } from 'react-router-dom';
import { createSplitGroup, lookupSplitUser } from '../../../api/endpoints';
import { Card, Field, Input, Button, Banner, Radio } from '../../../components/ui';
import './CreateGroupPage.css';

export default function CreateGroupPage() {
  const navigate = useNavigate();
  const [name, setName] = useState('');
  const [settlementMode, setSettlementMode] = useState('global');
  const [members, setMembers] = useState([]); // [{ id, username, included }]
  const [memberInput, setMemberInput] = useState('');
  const [memberError, setMemberError] = useState('');
  const [lookingUp, setLookingUp] = useState(false);
  const [error, setError] = useState('');
  const [submitting, setSubmitting] = useState(false);

  const handleAddMember = async (e) => {
    e.preventDefault();
    const username = memberInput.trim();
    if (!username) return;
    setMemberError('');
    if (members.some((m) => m.username === username)) {
      setMemberError('Already added.');
      return;
    }
    setLookingUp(true);
    try {
      const { data } = await lookupSplitUser(username);
      if (!data.found) {
        setMemberError(`No user found with the username "${username}".`);
      } else {
        setMembers((prev) => [...prev, { id: data.id, username: data.username, included: true }]);
        setMemberInput('');
      }
    } catch {
      setMemberError('Could not look up that username. Try again.');
    } finally {
      setLookingUp(false);
    }
  };

  const toggleMember = (id) => {
    setMembers((prev) => prev.map((m) => (m.id === id ? { ...m, included: !m.included } : m)));
  };

  const removeMember = (id) => {
    setMembers((prev) => prev.filter((m) => m.id !== id));
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    setError(''); setSubmitting(true);
    try {
      const member_ids = members.filter((m) => m.included).map((m) => m.id);
      const { data } = await createSplitGroup({ name, settlement_mode: settlementMode, member_ids });
      navigate(`/splits/${data.id}`);
    } catch (err) {
      const d = err.response?.data;
      setError(d?.name?.[0] || d?.detail || 'Could not create the group.');
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <div className="create-group">
      <Card>
        <form onSubmit={handleSubmit}>
          <Field label="Group name">
            <Input
              value={name} onChange={(e) => setName(e.target.value)}
              placeholder="e.g. Goa Trip" required maxLength={100}
            />
          </Field>

          <Field label="Members" hint="Add people by their username. You're added automatically.">
            <div className="create-group__add-member">
              <Input
                value={memberInput}
                onChange={(e) => setMemberInput(e.target.value)}
                placeholder="Enter a username"
                onKeyDown={(e) => { if (e.key === 'Enter') handleAddMember(e); }}
              />
              <Button type="button" variant="secondary" onClick={handleAddMember} disabled={lookingUp || !memberInput.trim()}>
                {lookingUp ? 'Looking up…' : '+ Add Member'}
              </Button>
            </div>
            {memberError && <p className="ui-field__error" role="alert">{memberError}</p>}
          </Field>

          {members.length > 0 && (
            <ul className="create-group__members">
              {members.map((m) => (
                <li key={m.id} className="create-group__member-row">
                  <label className="create-group__member-check">
                    <input type="checkbox" checked={m.included} onChange={() => toggleMember(m.id)} />
                    {m.username}
                  </label>
                  <button
                    type="button" className="create-group__member-remove"
                    onClick={() => removeMember(m.id)} aria-label={`Remove ${m.username}`}
                  >
                    ✕
                  </button>
                </li>
              ))}
            </ul>
          )}

          <Field label="Settlement mode" hint="You can change this later from the group.">
            <Radio
              name="settlement_mode" value="global" checked={settlementMode === 'global'}
              onChange={() => setSettlementMode('global')}
              label="Fewest payments" hint="Simplifies debts group-wide into the minimum number of transfers."
            />
            <Radio
              name="settlement_mode" value="pairwise" checked={settlementMode === 'pairwise'}
              onChange={() => setSettlementMode('pairwise')}
              label="Detailed" hint="Keeps a direct balance between every pair of members."
            />
          </Field>

          {error && <Banner tone="warn">{error}</Banner>}

          <div className="create-group__actions">
            <Button type="submit" disabled={submitting || !name.trim()}>
              {submitting ? 'Creating…' : 'Create Group'}
            </Button>
            <Link to="/splits"><Button type="button" variant="secondary">Cancel</Button></Link>
          </div>
        </form>
      </Card>
    </div>
  );
}
