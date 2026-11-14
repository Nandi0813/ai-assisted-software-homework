import { useState, type FormEvent } from 'react'
import { useMutation, useQueryClient } from '@tanstack/react-query'
import {
  createExpense,
  updateExpense,
  type Expense,
  type ExpenseRequest,
  type SplitRequest,
  type SplitType,
  type User,
} from '../api'

interface ExpenseFormProps {
  groupId: number
  members: User[]
  currentUserId: number
  editing: Expense | null
  onDone: () => void
}

function defaultPayer(members: User[], currentUserId: number): number {
  if (members.some((m) => m.id === currentUserId)) {
    return currentUserId
  }
  return members[0]?.id ?? currentUserId
}

export function ExpenseForm({
  groupId,
  members,
  currentUserId,
  editing,
  onDone,
}: ExpenseFormProps) {
  const queryClient = useQueryClient()
  const [description, setDescription] = useState(
    () => editing?.description ?? '',
  )
  const [amount, setAmount] = useState(() => editing?.amount ?? '')
  const [payerId, setPayerId] = useState(
    () => editing?.payer_id ?? defaultPayer(members, currentUserId),
  )
  const [splitType, setSplitType] = useState<SplitType>(
    () => editing?.split_type ?? 'equal',
  )
  const [excluded, setExcluded] = useState<Set<number>>(() =>
    editing !== null && editing.split_type === 'equal'
      ? new Set(
          members
            .filter((m) => !editing.shares.some((s) => s.user_id === m.id))
            .map((m) => m.id),
        )
      : new Set(),
  )
  const [values, setValues] = useState<Record<number, string>>(() => {
    const next: Record<number, string> = {}
    if (editing !== null) {
      for (const share of editing.shares) {
        next[share.user_id] =
          editing.split_type === 'percent'
            ? (share.percent ?? '')
            : share.amount
      }
    }
    return next
  })
  const [error, setError] = useState<string | null>(null)

  function resetToCreate() {
    setDescription('')
    setAmount('')
    setPayerId(defaultPayer(members, currentUserId))
    setSplitType('equal')
    setExcluded(new Set())
    setValues({})
  }

  const save = useMutation({
    mutationFn: (body: ExpenseRequest) =>
      editing === null
        ? createExpense(groupId, body)
        : updateExpense(groupId, editing.id, body),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ['expenses', groupId] })
      void queryClient.invalidateQueries({ queryKey: ['payments', groupId] })
      void queryClient.invalidateQueries({ queryKey: ['balances', groupId] })
      setError(null)
      resetToCreate()
      onDone()
    },
    onError: (e) => setError(e.message),
  })

  function buildSplit(): SplitRequest {
    if (splitType === 'equal') {
      return {
        type: 'equal',
        participants: members
          .filter((m) => !excluded.has(m.id))
          .map((m) => m.id),
      }
    }
    const filled = members.flatMap((m) => {
      const value = (values[m.id] ?? '').trim()
      return value === '' ? [] : [{ user_id: m.id, value }]
    })
    if (splitType === 'exact') {
      return {
        type: 'exact',
        shares: filled.map((s) => ({ user_id: s.user_id, amount: s.value })),
      }
    }
    return {
      type: 'percent',
      shares: filled.map((s) => ({ user_id: s.user_id, percent: s.value })),
    }
  }

  function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    save.mutate({
      description: description.trim(),
      amount: amount.trim(),
      payer_id: payerId,
      split: buildSplit(),
    })
  }

  function toggleExcluded(id: number) {
    setExcluded((prev) => {
      const next = new Set(prev)
      if (next.has(id)) {
        next.delete(id)
      } else {
        next.add(id)
      }
      return next
    })
  }

  function setValue(id: number, value: string) {
    setValues((prev) => ({ ...prev, [id]: value }))
  }

  const title = editing ? 'Edit expense' : 'Add expense'

  return (
    <form aria-label={title} onSubmit={handleSubmit}>
      <h3>{title}</h3>
      <div className="field-row">
        <label>
          Description
          <input
            value={description}
            onChange={(e) => setDescription(e.target.value)}
            required
            maxLength={200}
          />
        </label>
        <label>
          Amount
          <input
            value={amount}
            onChange={(e) => setAmount(e.target.value)}
            inputMode="decimal"
            required
            placeholder="0.00"
          />
        </label>
        <label>
          Paid by
          <select
            value={payerId}
            onChange={(e) => setPayerId(Number(e.target.value))}
          >
            {members.map((m) => (
              <option key={m.id} value={m.id}>
                {m.username}
              </option>
            ))}
          </select>
        </label>
      </div>
      <div className="field-row">
        <label>
          Split
          <select
            value={splitType}
            onChange={(e) => setSplitType(e.target.value as SplitType)}
          >
            <option value="equal">Equal</option>
            <option value="exact">Exact amounts</option>
            <option value="percent">Percentages</option>
          </select>
        </label>
        <fieldset>
          <legend>Participants</legend>
          {splitType === 'equal' &&
            members.map((m) => (
              <label key={m.id}>
                <input
                  type="checkbox"
                  checked={!excluded.has(m.id)}
                  onChange={() => toggleExcluded(m.id)}
                />{' '}
                {m.username}
              </label>
            ))}
          {splitType === 'exact' &&
            members.map((m) => (
              <label key={m.id}>
                {m.username} amount
                <input
                  inputMode="decimal"
                  value={values[m.id] ?? ''}
                  onChange={(e) => setValue(m.id, e.target.value)}
                />
              </label>
            ))}
          {splitType === 'percent' &&
            members.map((m) => (
              <label key={m.id}>
                {m.username} %
                <input
                  inputMode="decimal"
                  value={values[m.id] ?? ''}
                  onChange={(e) => setValue(m.id, e.target.value)}
                />
              </label>
            ))}
        </fieldset>
      </div>
      <div className="form-actions">
        <button type="submit" disabled={save.isPending}>
          {editing ? 'Save changes' : 'Add expense'}
        </button>
        {editing && (
          <button
            type="button"
            className="button-secondary"
            onClick={() => {
              resetToCreate()
              onDone()
            }}
          >
            Cancel
          </button>
        )}
      </div>
      {error !== null && <p role="alert">{error}</p>}
    </form>
  )
}
