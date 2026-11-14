import { useMutation, useQueryClient } from '@tanstack/react-query'
import { recordPayment, type Transfer } from '../api'

interface SettleUpPanelProps {
  groupId: number
  transfers: Transfer[]
}

export function SettleUpPanel({ groupId, transfers }: SettleUpPanelProps) {
  const queryClient = useQueryClient()
  const record = useMutation({
    mutationFn: (transfer: Transfer) =>
      recordPayment(groupId, {
        from_id: transfer.from_id,
        to_id: transfer.to_id,
        amount: transfer.amount,
      }),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ['expenses', groupId] })
      void queryClient.invalidateQueries({ queryKey: ['payments', groupId] })
      void queryClient.invalidateQueries({ queryKey: ['balances', groupId] })
    },
  })

  return (
    <section aria-label="Settle up">
      <h3>Settle up</h3>
      {transfers.length === 0 ? (
        <p>Everyone is settled up.</p>
      ) : (
        <ul>
          {transfers.map((transfer) => (
            <li key={`${transfer.from_id}-${transfer.to_id}`}>
              <span>
                {`${transfer.from_username} pays ${transfer.to_username} ${transfer.amount}`}
              </span>{' '}
              <button
                type="button"
                disabled={record.isPending}
                onClick={() => record.mutate(transfer)}
              >
                Record
              </button>
            </li>
          ))}
        </ul>
      )}
      {record.isError && <p role="alert">{record.error.message}</p>}
    </section>
  )
}
