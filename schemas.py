from pydantic import BaseModel, Field


class URLSummary(BaseModel):
    title: str = Field(description="The main title or headline of the webpage.")
    key_points: list[str] = Field(description="A list of 3 to 5 key bullet points summarizing the content.")
    category: str = Field(description="A single word category for this link (e.g., Technology, News, Opinion, Tutorial).")
