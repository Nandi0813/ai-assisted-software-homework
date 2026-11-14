import type { Balances } from '../api'

export function BalancesPanel({ balances }: { balances: Balances }) {
  return (
    <section aria-label="Balances">
      <h3>Balances</h3>
      <table>
        <thead>
          <tr>
            <th>Member</th>
            <th>Balance</th>
          </tr>
        </thead>
        <tbody>
          {balances.members.map((member) => {
            const isZero = member.balance === '0.00'
            const colour = isZero
              ? undefined
              : member.balance.startsWith('-')
                ? 'negative'
                : 'positive'
            return (
              <tr key={member.user_id}>
                <td>
                  {member.username}
                  {member.active ? '' : ' (former)'}
                </td>
                <td className={colour}>{member.balance}</td>
              </tr>
            )
          })}
        </tbody>
      </table>
    </section>
  )
}
