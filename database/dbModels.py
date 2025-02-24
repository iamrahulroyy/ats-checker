from sqlmodel import Field, SQLModel


class Resume(SQLModel, table=True):
    id: int = Field(default=None, primary_key=True)
    filename: str
    file_size: int
    file_url: str = None