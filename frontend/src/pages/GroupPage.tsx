import { useState, type FormEvent } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { Link, useNavigate, useParams } from 'react-router'
import {
  ApiError,
  addMember,
  getBalances,
  getGroup,
  leaveGroup,
  listExpenses,
  listPayments,
  type Expense,
} from '../api'
import { useAuth } from '../auth-context'
import { BalancesPanel } from '../components/BalancesPanel'
import { ExpenseForm } from '../components/ExpenseForm'
import { ExpenseList } from '../components/ExpenseList'
import { PaymentForm } from '../components/PaymentForm'
import { PaymentList } from '../components/PaymentList'
import { SettleUpPanel } from '../components/SettleUpPanel'

export function GroupPage() {
  const groupId = Number(useParams().groupId)
  const navigate = useNavigate()
  const queryClient = useQueryClient()
  const { user } = useAuth()
  const [username, setUsername] = useState('')
  const [editing, setEditing] = useState<Expense | null>(null)
  const group = useQuery({
    queryKey: ['group', groupId],
    queryFn: () => getGroup(groupId),
  })
  const expenses = useQuery({
    queryKey: ['expenses', groupId],
    queryFn: () => listExpenses(groupId),
    enabled: group.isSuccess,
  })
  const payments = useQuery({
    queryKey: ['payments', groupId],
    queryFn: () => listPayments(groupId),
    enabled: group.isSuccess,
  })
  const balances = useQuery({
    queryKey: ['balances', groupId],
    queryFn: () => getBalances(groupId),
    enabled: group.isSuccess,
  })
  const add = useMutation({
    mutationFn: (name: string) => addMember(groupId, name),
    onSuccess: (detail) => {
      queryClient.setQueryData(['group', groupId], detail)
      setUsername('')
    },
  })
  const leave = useMutation({
    mutationFn: () => leaveGroup(groupId),
    onSuccess: () => {
      queryClient.removeQueries({ queryKey: ['group', groupId] })
      queryClient.removeQueries({ queryKey: ['expenses', groupId] })
      queryClient.removeQueries({ queryKey: ['payments', groupId] })
      queryClient.removeQueries({ queryKey: ['balances', groupId] })
      queryClient.invalidateQueries({ queryKey: ['groups'] })
      navigate('/')
    },
  })

  function handleAdd(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    add.mutate(username)
  }

  if (user === null) {
    return null
  }
  if (group.isPending) {
    return <p>Loading…</p>
  }
  if (group.isError) {
    if (group.error instanceof ApiError && group.error.status === 404) {
      return (
        <section>
          <p role="alert">Group not found.</p>
          <Link to="/">Back to groups</Link>
        </section>
      )
    }
    return <p role="alert">{group.error.message}</p>
  }

  const detail = group.data
  const names = new Map<number, string>(
    [...detail.members, ...detail.former_members].map(
      (member): [number, string] => [member.id, member.username],
    ),
  )
  const nameOf = (id: number): string => names.get(id) ?? `user #${id}`
  return (
    <>
      <h2>{detail.name}</h2>
      <section aria-label="Members">
        <h3>Members</h3>
        <ul>
          {detail.members.map((member) => (
            <li key={member.id}>{member.username}</li>
          ))}
        </ul>
      </section>
      {detail.former_members.length > 0 && (
        <section>
          <h3>Former members</h3>
          <ul>
            {detail.former_members.map((member) => (
              <li key={member.id}>{member.username}</li>
            ))}
          </ul>
        </section>
      )}
      {balances.isPending ? (
        <p>Loading…</p>
      ) : balances.isError ? (
        <p role="alert">{balances.error.message}</p>
      ) : (
        <BalancesPanel balances={balances.data} />
      )}
      {balances.isPending ? (
        <p>Loading…</p>
      ) : balances.isError ? (
        <p role="alert">{balances.error.message}</p>
      ) : (
        <SettleUpPanel groupId={groupId} transfers={balances.data.transfers} />
      )}
      <section>
        <ExpenseForm
          key={editing === null ? 'new' : `edit-${editing.id}`}
          groupId={groupId}
          members={detail.members}
          currentUserId={user.id}
          editing={editing}
          onDone={() => setEditing(null)}
        />
      </section>
      {expenses.isPending ? (
        <p>Loading…</p>
      ) : expenses.isError ? (
        <p role="alert">{expenses.error.message}</p>
      ) : (
        <ExpenseList
          groupId={groupId}
          expenses={expenses.data}
          currentUserId={user.id}
          nameOf={nameOf}
          onEdit={setEditing}
        />
      )}
      <section>
        <PaymentForm
          groupId={groupId}
          members={detail.members}
          currentUserId={user.id}
        />
      </section>
      {payments.isPending ? (
        <p>Loading…</p>
      ) : payments.isError ? (
        <p role="alert">{payments.error.message}</p>
      ) : (
        <PaymentList payments={payments.data} nameOf={nameOf} />
      )}
      <section>
        <form onSubmit={handleAdd}>
          <label>
            Add member by username
            <input
              value={username}
              onChange={(e) => setUsername(e.target.value)}
              required
            />
          </label>
          <button type="submit">Add member</button>
        </form>
        {add.isError && <p role="alert">{add.error.message}</p>}
      </section>
      <section>
        <button type="button" onClick={() => leave.mutate()}>
          Leave group
        </button>
        {leave.isError && <p role="alert">{leave.error.message}</p>}
      </section>
    </>
  )
}
