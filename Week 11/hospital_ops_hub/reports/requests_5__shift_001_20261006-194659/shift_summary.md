# Shift 1 report
Started: 2026-10-06T19:46:54  
Generated: 2026-10-06T19:46:59

## Resource snapshot
- Waiting patients: 3
- Admitted patients: 6
- Available doctors: 1
- Free beds: 2
- Available staff: 3

## Assigned (4)
- R02 (er_emergency, emergency): Patient Agent: registered Unknown (R02) as P008; Bed Agent: ER bed B01; Doctor Agent: Dr. Meera Nair (cardiology, load 1); Staff Agent > ER Support Dispatch: Murugan S (porter, stretcher)
- R04 (er_emergency, emergency): Patient Agent: registered Unknown (R04) as P009; Bed Agent: ER bed B02; Doctor Agent: no free neurology doctor (D02 is busy) -> spawning reallocation_worker; Staff Agent > ER Support Dispatch: no available porter/nurse with stretcher [PT01 already granted to a higher-priority request] -> spawning staffing_gap_resolver; Reallocation Worker: pulled Dr. Arjun Menon (neurology) off routine work for ER (P002 follow-up deferred; P003 follow-up deferred); Staffing Gap Resolver: covered by Nisha George (float_pool, available)
- R01 (new_patient, routine): Patient Agent: registered Neha Iyer as P007; Doctor Agent: Dr. Kavitha Rao (general_medicine, load 0); Staff Agent > Clerk Dispatch: Priya Raman (clerk, registration)
- R03 (cleaning, routine): Staff Agent > Housekeeping Dispatcher: Housekeeping Team A (cleaning, standard)

## Queued (1)
- R05 (patient_handling, routine): Patient Agent: existing patient P004 (Anitha Selvam) confirmed; Staff Agent > Handling Dispatcher: no available porter/nurse with wheelchair [PT01 already granted to a higher-priority request] -> spawning staffing_gap_resolver; staff: float pool and on-call exhausted for wheelchair [FL01 already granted to a higher-priority request]

## Escalated (0)
- none

## Free beds by ward
- General: 2