# SplitLedger: Specification

**Author:** Nandor Dukat · **Email:** dukatnandor@gmail.com

## Objective
A web app for sharing expenses in a group, like flatmates or a trip. Members record who paid and who shared each expense. The app keeps every member's balance and suggests transfers to settle up. It has a FastAPI backend with SQLite storage and a React frontend.

## Roles
- **Visitor:** can only register or log in.
- **Member:** a logged-in user who belongs to a group. Members can view and change only the groups they belong to.

## Main scenarios
1. A user registers, creates a group and adds other registered users by username.
2. A member adds an expense: description, amount, payer and participants. The split is equal, exact amounts or percentages.
3. A member views each member's balance and the suggested settle-up transfers.
4. A member records a payment to another member, which changes both balances.
5. A member leaves a group.

## Acceptance criteria
1. **Equal split:** Alice pays 90.00 for Alice, Bob and Cecil. Balances become Alice +60.00, Bob −30.00 and Cecil −30.00.
2. **Rounding:** 100.00 split equally among 3 gives shares of 33.34, 33.33 and 33.33. Shares always add up exactly to the total. Leftover cents go one each to participants in the order they joined the group.
3. **Custom split check:** an exact split must add up to the total, and a percentage split must add up to 100%. Otherwise the request is rejected with HTTP 422 and a message, and nothing is saved.
4. **Invalid input:** each of these is rejected with HTTP 422 and no data changes: an amount of 0, a negative amount, more than 2 decimal places, more than 1,000,000.00, an empty participant list, or a payer or participant who isn't in the group.
5. **Authorisation:** an unauthenticated request gets HTTP 401. A logged-in non-member reading or changing a group gets HTTP 404, and the response doesn't reveal that the group exists.
6. **Settle-up:** for any balances, the suggested list has at most n−1 transfers for n members with a non-zero balance. Recording every suggested transfer brings all balances to 0.00.
7. **Leaving a group:** a member with a non-zero balance can't leave (HTTP 409, and the UI shows the outstanding amount). A member with a 0.00 balance can leave. Their past expenses stay in the group's history.
8. **Persistence:** groups, expenses and payments are still there after the backend restarts, and balances stay the same.

## Uncertainties and chosen interpretation
- **Currency:** one currency per group with 2 decimal places. Amounts are stored as whole cents to avoid floating-point errors.
- **Optimal settle-up:** the true minimum number of transfers is NP-hard to find. A greedy matching of the largest creditor with the largest debtor is used. It guarantees at most n−1 transfers (criterion 6), not the absolute minimum.
- **Editing and deleting:** only the member who created an expense can edit or delete it. Balances are then recalculated.
- **Adding members:** any member can add a registered user by username. There are no invitations or confirmation steps.
- **The payer as participant:** the payer doesn't have to share in an expense. For example, someone can buy something only for others.
- **Status code for non-members:** HTTP 404 is used instead of 403 so that group IDs can't be discovered by probing.
