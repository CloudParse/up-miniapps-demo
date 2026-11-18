from app.schemas.hello import Greeting


class HelloService:
    """Business logic for greetings. Knows nothing about HTTP."""

    def greet(self, name: str) -> Greeting:
        return Greeting(message=f"Hello, {name}!")
