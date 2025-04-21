from abc import ABC, abstractmethod



class BaseLLM(ABC):
    @abstractmethod
    def generate_response(self, params):
        pass
