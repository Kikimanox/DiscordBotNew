from dataclasses import dataclass, field
from typing import Optional, List


@dataclass
class ClubData:
    club_name: str
    club_data: dict
    creator_id: Optional[int] = 0
    creator_name: Optional[str] = ""
    description: Optional[str] = ""
    pings: Optional[int] = 0
    members: List[int] = field(default_factory=list)

    def __post_init__(self):
        data = self.club_data

        self.creator_id = data.get("creator")
        self.description = data.get("desc")
        self.pings = data.get("pings")
        self.members = data.get("members")
