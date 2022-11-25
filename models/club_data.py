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
    member_count: int = 0
    members: List[int] = field(default_factory=list)

    def __post_init__(self):
        data = self.club_data

        self.creator_id = data.get("creator")
        self.description = data.get("desc")
        self.pings = data.get("pings")
        self.members = data.get("members")
        self.member_count = len(self.members)

    def check_if_author_is_in_the_club(
            self,
            author_id: int
    ) -> bool:
        if author_id in self.members:
            return True
        else:
            return False

    def check_if_all_of_list_exist_on_this_club(
            self,
            memberList: List[int]
    ) -> bool:
        check = all(item in self.members for item in memberList)
        return check
