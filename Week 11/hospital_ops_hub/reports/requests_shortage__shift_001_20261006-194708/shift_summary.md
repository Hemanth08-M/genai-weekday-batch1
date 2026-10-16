# Shift 1 report
Started: 2026-10-06T19:47:04  
Generated: 2026-10-06T19:47:08

## Resource snapshot
- Waiting patients: 4
- Admitted patients: 6
- Available doctors: 1
- Free beds: 2
- Available staff: 5

## Assigned (1)
- X01 (er_emergency, emergency): Patient Agent: registered Unknown (X01) as P007; Bed Agent: ER bed B01; Doctor Agent: Dr. Meera Nair (cardiology, load 1); Staff Agent > ER Support Dispatch: Murugan S (porter, stretcher)

## Queued (0)
- none

## Escalated (3)
- X02 (er_emergency, emergency): Patient Agent: registered Unknown (X02) as P008; Bed Agent: ER bed B02; Doctor Agent: every eligible cardiology doctor was taken [D01 already granted to a higher-priority request] -> spawning reallocation_worker; Staff Agent > ER Support Dispatch: no available porter/nurse with stretcher [PT01 already granted to a higher-priority request] -> spawning staffing_gap_resolver; Staffing Gap Resolver: covered by Nisha George (float_pool, available); doctor: no doctor could be reallocated
- X03 (er_emergency, emergency): Patient Agent: registered Unknown (X03) as P009; Doctor Agent: no free neurology doctor (D02 is busy) -> spawning reallocation_worker; Staff Agent > ER Support Dispatch: no available porter/nurse with stretcher [PT01 already granted to a higher-priority request] -> spawning staffing_gap_resolver; Reallocation Worker: pulled Dr. Arjun Menon (neurology) off routine work for ER (P002 follow-up deferred; P003 follow-up deferred); bed: ER ward full, no discharge-ready bed [B01 already granted to a higher-priority request; B02 already granted to a higher-priority request]; staff: float pool and on-call exhausted for stretcher [FL01 already granted to a higher-priority request]
- X04 (er_emergency, emergency): Patient Agent: registered Unknown (X04) as P010; Doctor Agent: no free neurology doctor (D02 is busy) -> spawning reallocation_worker; Staff Agent > ER Support Dispatch: no available porter/nurse with stretcher [PT01 already granted to a higher-priority request] -> spawning staffing_gap_resolver; bed: ER ward full, no discharge-ready bed [B01 already granted to a higher-priority request; B02 already granted to a higher-priority request]; doctor: no doctor could be reallocated [D02 already granted to a higher-priority request]; staff: float pool and on-call exhausted for stretcher [FL01 already granted to a higher-priority request]

## Free beds by ward
- General: 2