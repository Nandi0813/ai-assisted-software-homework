import type { Payment } from '../api'

interface PaymentListProps {
  payments: Payment[]
  nameOf: (id: number) => string
}

export function PaymentList({ payments, nameOf }: PaymentListProps) {
  return (
    <section aria-label="Payments">
      <h3>Payments</h3>
      {payments.length === 0 ? (
        <p>No payments yet.</p>
      ) : (
        <ul>
          {payments.map((payment) => (
            <li key={payment.id}>
              {`${nameOf(payment.from_id)} paid ${nameOf(payment.to_id)} ${payment.amount}`}
            </li>
          ))}
        </ul>
      )}
    </section>
  )
}
