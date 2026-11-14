import type { Balances } from '../api'

export function BalancesPanel({ balances }: { balances: Balances }) {
  // Drawing only: the bar lengths are scaled from the largest balance shown.
  const maxAbs = Math.max(
    0,
    ...balances.members.map((m) => Math.abs(Number(m.balance))),
  )
  return (
    <section aria-label="Balances">
      <h3>Balances</h3>
      <div className="table-wrap">
        <table>
          <thead>
            <tr>
              <th>Member</th>
              <th>Balance</th>
              <th aria-hidden="true" className="bar-head" />
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
              const value = Number(member.balance)
              const pct =
                maxAbs === 0 ? 0 : Math.round((Math.abs(value) / maxAbs) * 100)
              return (
                <tr key={member.user_id}>
                  <td>
                    {member.username}
                    {member.active ? '' : ' (former)'}
                  </td>
                  <td className={colour}>{member.balance}</td>
                  <td aria-hidden="true" className="bar-cell">
                    <div className="track">
                      <div className="half left">
                        {value < 0 && (
                          <span
                            className="fill owes"
                            style={{ width: `${pct}%` }}
                          />
                        )}
                      </div>
                      <div className="half right">
                        {value > 0 && (
                          <span
                            className="fill owed"
                            style={{ width: `${pct}%` }}
                          />
                        )}
                      </div>
                    </div>
                  </td>
                </tr>
              )
            })}
          </tbody>
        </table>
      </div>
    </section>
  )
}
