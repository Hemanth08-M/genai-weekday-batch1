"""The four resource manager agents, each owning one list."""
from .bed_agent import BedAgent
from .doctor_agent import DoctorAgent
from .patient_agent import PatientAgent
from .staff_agent import StaffAgent

AGENTS = {
    "patient_agent": PatientAgent(),
    "doctor_agent": DoctorAgent(),
    "bed_agent": BedAgent(),
    "staff_agent": StaffAgent(),
}
