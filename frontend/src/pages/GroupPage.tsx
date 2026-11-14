import { useState, type FormEvent } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { Link, useNavigate, useParams } from 'react-router'
import { ApiError, addMember, getGroup, leaveGroup } from '../api'
import { SettleUpPanel } from '../components/SettleUpPanel'

export function GroupPage() {
  const groupId = Number(useParams().groupId)
  const navigate = useNavigate()
  const queryClient = useQueryClient()
  const [username, setUsername] = useState('')
  const group = useQuery({
    queryKey: ['group', groupId],
    queryFn: () => getGroup(groupId),
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
      queryClient.invalidateQueries({ queryKey: ['groups'] })
      navigate('/')
    },
  })

  function handleAdd(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    add.mutate(username)
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
      <SettleUpPanel groupId={groupId} />
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
