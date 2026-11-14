import { useState, type FormEvent } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { Link, useNavigate } from 'react-router'
import { createGroup, listGroups } from '../api'

export function GroupsPage() {
  const navigate = useNavigate()
  const queryClient = useQueryClient()
  const [name, setName] = useState('')
  const groups = useQuery({ queryKey: ['groups'], queryFn: listGroups })
  const create = useMutation({
    mutationFn: createGroup,
    onSuccess: (group) => {
      queryClient.invalidateQueries({ queryKey: ['groups'] })
      setName('')
      navigate(`/groups/${group.id}`)
    },
  })

  function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    create.mutate(name)
  }

  return (
    <div className="narrow">
      <section>
        <h2>Your groups</h2>
        {groups.isPending && <p>Loading…</p>}
        {groups.isError && <p role="alert">{groups.error.message}</p>}
        {groups.data?.length === 0 && <p>No groups yet.</p>}
        {groups.data !== undefined && groups.data.length > 0 && (
          <ul className="group-list">
            {groups.data.map((group) => (
              <li key={group.id}>
                <Link to={`/groups/${group.id}`}>{group.name}</Link>
              </li>
            ))}
          </ul>
        )}
      </section>
      <section className="panel">
        <form onSubmit={handleSubmit}>
          <label>
            New group name
            <input
              value={name}
              onChange={(e) => setName(e.target.value)}
              required
              maxLength={64}
            />
          </label>
          <button type="submit">Create group</button>
        </form>
        {create.isError && <p role="alert">{create.error.message}</p>}
      </section>
    </div>
  )
}
