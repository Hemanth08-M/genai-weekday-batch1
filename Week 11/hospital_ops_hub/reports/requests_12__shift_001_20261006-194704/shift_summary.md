# Shift 1 report
Started: 2026-10-06T19:46:59  
Generated: 2026-10-06T19:47:04

## Resource snapshot
- Waiting patients: 2
- Admitted patients: 8
- Available doctors: 1
- Free beds: 0
- Available staff: 1

## Assigned (8)
- R02 (er_emergency, emergency): Patient Agent: registered Unknown (R02) as P008; Bed Agent: ER bed B01; Doctor Agent: Dr. Meera Nair (cardiology, load 1); Staff Agent > ER Support Dispatch: Murugan S (porter, stretcher)
- R04 (er_emergency, emergency): Patient Agent: registered Unknown (R04) as P009; Bed Agent: ER bed B02; Doctor Agent: no free neurology doctor (D02 is busy) -> spawning reallocation_worker; Staff Agent > ER Support Dispatch: no available porter/nurse with stretcher [PT01 already granted to a higher-priority request] -> spawning staffing_gap_resolver; Reallocation Worker: pulled Dr. Arjun Menon (neurology) off routine work for ER (P003 follow-up deferred); Staffing Gap Resolver: covered by Nisha George (float_pool, available)
- R06 (cleaning, urgent): Staff Agent > Housekeeping Dispatcher (biohazard team): Housekeeping Team B (cleaning, biohazard)
- R07 (emergency_admission, urgent): Patient Agent: registered Rahul Dev as P010; Bed Agent: ICU full -> discharged ready patient P002 (Lakshmi Devi) to free B04
- R01 (new_patient, routine): Patient Agent: registered Neha Iyer as P007; Doctor Agent: Dr. Kavitha Rao (general_medicine, load 0); Staff Agent > Clerk Dispatch: Priya Raman (clerk, registration)
- R03 (cleaning, routine): Staff Agent > Housekeeping Dispatcher: Housekeeping Team A (cleaning, standard)
- R09 (routine_bed, routine): Patient Agent: existing patient P005 (Mohammed Farook) confirmed; Bed Agent: General bed B07
- R11 (routine_bed, routine): Patient Agent: existing patient P006 (Divya Prakash) confirmed; Bed Agent: General bed B08

## Queued (2)
- R05 (patient_handling, routine): Patient Agent: existing patient P004 (Anitha Selvam) confirmed; Staff Agent > Handling Dispatcher: no available porter/nurse with wheelchair [PT01 already granted to a higher-priority request] -> spawning staffing_gap_resolver; staff: float pool and on-call exhausted for wheelchair [FL01 already granted to a higher-priority request]
- R08 (new_patient, routine): Patient Agent: registered Gopal Krishnan as P011; Staff Agent > Clerk Dispatch: Vignesh Kumar (clerk, registration); doctor: no free orthopedics doctor (D04 is busy)

## Escalated (2)
- R10 (patient_handling, urgent): Staff Agent > Handling Dispatcher: no available porter/nurse with stretcher [PT01 already granted to a higher-priority request] -> spawning staffing_gap_resolver; staff: float pool and on-call exhausted for stretcher [FL01 already granted to a higher-priority request]
- R12 (malformed, urgent): malformed request: missing timestamp, description has no actionable details

## Free beds by ward
- none