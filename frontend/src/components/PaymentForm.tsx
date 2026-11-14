import { useState, type FormEvent } from 'react'
import { useMutation, useQueryClient } from '@tanstack/react-query'
import { recordPayment, type User } from '../api'

interface PaymentFormProps {
  groupId: number
  members: User[]
  currentUserId: number
}

function defaultFrom(members: User[], currentUserId: number): number {
  if (members.some((m) => m.id === currentUserId)) {
    return currentUserId
  }
  return members[0]?.id ?? currentUserId
}

function defaultTo(members: User[], fromId: number): number {
  const other = members.find((m) => m.id !== fromId)
  return other?.id ?? fromId
}

export function PaymentForm({
  groupId,
  members,
  currentUserId,
}: PaymentFormProps) {
  const queryClient = useQueryClient()
  const [fromId, setFromId] = useState(() =>
    defaultFrom(members, currentUserId),
  )
  const [toId, setToId] = useState<number | null>(null)
  const effectiveTo = toId ?? defaultTo(members, fromId)
  const [amount, setAmount] = useState('')
  const [error, setError] = useState<string | null>(null)

  const record = useMutation({
    mutationFn: (body: { from_id: number; to_id: number; amount: string }) =>
      recordPayment(groupId, body),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ['expenses', groupId] })
      void queryClient.invalidateQueries({ queryKey: ['payments', groupId] })
      void queryClient.invalidateQueries({ queryKey: ['balances', groupId] })
      setAmount('')
      setError(null)
    },
    onError: (e) => setError(e.message),
  })

  function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    record.mutate({
      from_id: fromId,
      to_id: effectiveTo,
      amount: amount.trim(),
    })
  }

  return (
    <form aria-label="Record payment" onSubmit={handleSubmit}>
      <h3>Record payment</h3>
      <label>
        From
        <select
          value={fromId}
          onChange={(e) => setFromId(Number(e.target.value))}
        >
          {members.map((m) => (
            <option key={m.id} value={m.id}>
              {m.username}
            </option>
          ))}
        </select>
      </label>
      <label>
        To
        <select
          value={effectiveTo}
          onChange={(e) => setToId(Number(e.target.value))}
        >
          {members.map((m) => (
            <option key={m.id} value={m.id}>
              {m.username}
            </option>
          ))}
        </select>
      </label>
      <label>
        Payment amount
        <input
          value={amount}
          onChange={(e) => setAmount(e.target.value)}
          inputMode="decimal"
          required
        />
      </label>
      <button type="submit">Record payment</button>
      {error !== null && <p role="alert">{error}</p>}
    </form>
  )
}
