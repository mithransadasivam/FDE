# Working an overdue KYC exception: the bank's playbook

*From Grace Mensah (KYC operations, North) and Helen Achebe (MLRO). All data is fictional.*

An exception is worked when its outcome is recorded in **CaseFlow Classic**, the bank's case system, and the exception has a comment that says what was recorded and its reference.

## 1. Read before you decide

1. The exception (KX-…): its kind and its case.
2. The customer in the CRM (CU-…): the risk rating.
3. The documents on the customer's file in the document store.
4. The case in CaseFlow Classic (KC-…): its status and its case history.

## 2. Choose the outcome: the first rule that matches wins

| # | When | Outcome | Reason code |
|---|---|---|---|
| 1 | The exception is an **escalation** | Refer to Financial Crime | R04 Financial crime concern |
| 2 | The customer's risk rating is **high** | Refer to Financial Crime | R05 High-risk customer |
| 3 | The exception is an **applicant follow-up**, and the applicant has not replied since we asked | Chase applicant | R06 No reply from applicant |
| 4 | No proof of identity on file (a **passport** or a **driving licence**) | Request more information | R01 Missing proof of identity |
| 5 | No proof of address on file (a **utility bill**, **bank statement** or **council tax bill**) | Request more information | R02 Missing proof of address |
| 6 | Otherwise | Ready for decision | R03 Documents complete |

## 3. Record it in CaseFlow Classic

Find the case, press **Record outcome**, choose the outcome and the reason code, write a short note (at most 240 characters), press **Save**, check the confirm screen, then press **Confirm**. CaseFlow shows a reference (OUT-…).

## 4. Close the loop

Add a comment to the exception: the outcome, the reason code and the CaseFlow reference.

## Never

- Never withdraw a case. Only an analyst withdraws a case, by hand, after speaking to the applicant.
- Never record an outcome on a record that another person has locked. Stop, and hand the exception back.
- Never put anything in a note that the applicant has not been told.
