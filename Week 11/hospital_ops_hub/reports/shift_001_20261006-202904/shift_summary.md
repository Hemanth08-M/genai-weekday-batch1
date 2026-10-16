# Shift 1 report
Started: 2026-10-06T20:23:18  
Generated: 2026-10-06T20:29:04

## Resource snapshot
- Waiting patients: 3
- Admitted patients: 6
- Available doctors: 2
- Free beds: 2
- Available staff: 3

## Assigned (4)
- R04 (er_emergency, emergency): Patient Agent: registered Unknown (R04) as P009; Bed Agent: ER bed B02; Doctor Agent: no free neurology doctor (D02 is busy) -> spawning reallocation_worker; Staff Agent > ER Support Dispatch: no available porter/nurse with stretcher [PT01 already granted to a higher-priority request] -> spawning staffing_gap_resolver; Reallocation Worker: pulled Dr. Arjun Menon (neurology) off routine work for ER (P002 follow-up deferred; P003 follow-up deferred); Staffing Gap Resolver: covered by Nisha George (float_pool, available)
- R01 (new_patient, routine): Patient Agent: registered Neha Iyer as P007; Doctor Agent: Dr. Kavitha Rao (general_medicine, load 0); Staff Agent > Clerk Dispatch: Priya Raman (clerk, registration)
- R03 (cleaning, routine): Staff Agent > Housekeeping Dispatcher: Housekeeping Team A (cleaning, standard)
- R05-retry (patient_handling, routine): Patient Agent: existing patient P004 (Anitha Selvam) confirmed; Staff Agent > Handling Dispatcher: Murugan S (porter, wheelchair)

## Queued (0)
- none

## Escalated (0)
- none

## Completed (1)
- R02 (er_emergency, emergency): Patient Agent: registered Unknown (R02) as P008; Bed Agent: ER bed B01; Doctor Agent: Dr. Meera Nair (cardiology, load 1); Staff Agent > ER Support Dispatch: Murugan S (porter, stretcher); completed at 2026-10-02T10:00; released staff PT01; doctor D01 back to available

## Retried (1)
- R05 (patient_handling, routine): re-run as R05-retry -> assigned

## Free beds by ward
- General: 2