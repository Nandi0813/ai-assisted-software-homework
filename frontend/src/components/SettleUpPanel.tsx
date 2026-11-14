import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { getBalances, recordPayment, type Transfer } from '../api'

export function SettleUpPanel({ groupId }: { groupId: number }) {
  const queryClient = useQueryClient()
  const balances = useQuery({
    queryKey: ['balances', groupId],
    queryFn: () => getBalances(groupId),
  })
  const record = useMutation({
    mutationFn: (t: Transfer) =>
      recordPayment(groupId, {
        from_id: t.from_id,
        to_id: t.to_id,
        amount: t.amount,
      }),
    onSuccess: () =>
      queryClient.invalidateQueries({ queryKey: ['balances', groupId] }),
  })

  return (
    <section aria-label="Settle up">
      <h3>Settle up</h3>
      {balances.isPending && <p>Loading…</p>}
      {balances.isError && <p role="alert">{balances.error.message}</p>}
      {balances.isSuccess &&
        (balances.data.transfers.length === 0 ? (
          <p>Everyone is settled up.</p>
        ) : (
          <ul>
            {balances.data.transfers.map((t) => (
              <li key={`${t.from_id}-${t.to_id}`}>
                {t.from_username} pays {t.to_username} {t.amount}{' '}
                <button
                  type="button"
                  disabled={record.isPending}
                  onClick={() => record.mutate(t)}
                >
                  Record {t.from_username} → {t.to_username}
                </button>
              </li>
            ))}
          </ul>
        ))}
      {record.isError && <p role="alert">{record.error.message}</p>}
    </section>
  )
}
