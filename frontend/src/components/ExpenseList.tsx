import { useMutation, useQueryClient } from '@tanstack/react-query'
import { deleteExpense, type Expense } from '../api'

interface ExpenseListProps {
  groupId: number
  expenses: Expense[]
  currentUserId: number
  nameOf: (id: number) => string
  onEdit: (expense: Expense) => void
}

export function ExpenseList({
  groupId,
  expenses,
  currentUserId,
  nameOf,
  onEdit,
}: ExpenseListProps) {
  const queryClient = useQueryClient()
  const remove = useMutation({
    mutationFn: (expenseId: number) => deleteExpense(groupId, expenseId),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ['expenses', groupId] })
      void queryClient.invalidateQueries({ queryKey: ['payments', groupId] })
      void queryClient.invalidateQueries({ queryKey: ['balances', groupId] })
    },
  })

  return (
    <section aria-label="Expenses">
      <h3>Expenses</h3>
      {expenses.length === 0 ? (
        <p>No expenses yet.</p>
      ) : (
        <table>
          <thead>
            <tr>
              <th>Description</th>
              <th>Amount</th>
              <th>Paid by</th>
              <th>Shares</th>
              <th></th>
            </tr>
          </thead>
          <tbody>
            {expenses.map((expense) => (
              <tr key={expense.id}>
                <td>{expense.description}</td>
                <td>{expense.amount}</td>
                <td>{nameOf(expense.payer_id)}</td>
                <td>
                  {expense.shares
                    .map(
                      (s) =>
                        `${nameOf(s.user_id)} ${s.amount}` +
                        (s.percent !== null ? ` (${s.percent}%)` : ''),
                    )
                    .join(', ')}
                </td>
                <td>
                  {expense.created_by === currentUserId && (
                    <>
                      <button type="button" onClick={() => onEdit(expense)}>
                        Edit
                      </button>
                      <button
                        type="button"
                        onClick={() => remove.mutate(expense.id)}
                      >
                        Delete
                      </button>
                    </>
                  )}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
      {remove.isError && <p role="alert">{remove.error.message}</p>}
    </section>
  )
}
