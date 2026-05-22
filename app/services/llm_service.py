import os
import logging
from typing import Dict, Any, Optional, Generator
import ollama
from ollama import AsyncClient

logger = logging.getLogger(__name__)

class LLMService:
    def __init__(self):
        self.host = os.getenv("OLLAMA_HOST", "http://127.0.0.1:11434")
        self.model = os.getenv("OLLAMA_MODEL", "llama3.1:8b-instruct-q4_K_M")
        self.embed_model = os.getenv("OLLAMA_EMBED_MODEL", "nomic-embed-text")
        self.client = None
        self.model_loaded = False
        self.last_use_time = None
        self._initialize()

    def _initialize(self):
        try:
            os.environ['OLLAMA_HOST'] = self.host
            self.client = ollama.Client(host=self.host)
            
            try:
                self.client.show(self.model)
                self.model_loaded = True
                logger.info(f"Ollama model verified: {self.model}")
            except Exception:
                logger.warning(f"Model {self.model} not found, will attempt to pull on first use")
                self.model_loaded = False
                
        except Exception as e:
            logger.error(f"Failed to initialize Ollama client: {str(e)}")
            self.client = None

    def generate_response(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        context: Optional[str] = None,
        temperature: float = 0.7,
        max_tokens: int = 2048,
        stream: bool = False
    ) -> Dict[str, Any]:
        if not self.client:
            raise RuntimeError("Ollama client not initialized")

        full_prompt = prompt
        if context:
            full_prompt = f"Context:\n{context}\n\n{prompt}"
        
        messages = []
        if system_prompt:
            messages.append({
                'role': 'system',
                'content': system_prompt
            })
        messages.append({
            'role': 'user',
            'content': full_prompt
        })
        
        try:
            if stream:
                return self._generate_stream(messages, temperature, max_tokens)
            
            response = self.client.chat(
                model=self.model,
                messages=messages,
                options={
                    'temperature': temperature,
                    'num_predict': max_tokens,
                    'stop': ['</s>', 'USER:', 'ASSISTANT:']
                }
            )
            
            self.last_use_time = __import__('time').time()
            
            return {
                'response': response['message']['content'],
                'model': self.model,
                'done': True,
                'total_duration': response.get('total_duration', 0),
                'eval_count': response.get('eval_count', 0)
            }
            
        except Exception as e:
            logger.error(f"Generation error: {str(e)}")
            if 'model not found' in str(e).lower():
                logger.info(f"Pulling model {self.model}...")
                self._pull_model()
                return self.generate_response(prompt, system_prompt, context, temperature, max_tokens, stream)
            raise RuntimeError(f"Failed to generate response: {str(e)}")

    def _generate_stream(
        self,
        messages: list,
        temperature: float,
        max_tokens: int
    ) -> Generator[str, None, None]:
        try:
            stream_response = self.client.chat(
                model=self.model,
                messages=messages,
                stream=True,
                options={
                    'temperature': temperature,
                    'num_predict': max_tokens
                }
            )
            
            for chunk in stream_response:
                if 'message' in chunk and 'content' in chunk['message']:
                    yield chunk['message']['content']
            
            self.last_use_time = __import__('time').time()
            
        except Exception as e:
            logger.error(f"Stream generation error: {str(e)}")
            raise RuntimeError(f"Failed to stream response: {str(e)}")

    def generate_with_retry(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        context: Optional[str] = None,
        max_retries: int = 3,
        temperature: float = 0.7
    ) -> Dict[str, Any]:
        for attempt in range(max_retries):
            try:
                return self.generate_response(
                    prompt,
                    system_prompt,
                    context,
                    temperature
                )
            except RuntimeError as e:
                if attempt == max_retries - 1:
                    raise
                logger.warning(f"Attempt {attempt + 1} failed: {str(e)}, retrying...")
                __import__('time').sleep(2 ** attempt)

    def embed_text(self, text: str) -> list:
        if not self.client:
            raise RuntimeError("Ollama client not initialized")
        
        try:
            response = self.client.embeddings(
                model=self.embed_model,
                prompt=text
            )
            
            return response['embedding']
            
        except Exception as e:
            logger.error(f"Embedding error: {str(e)}")
            raise RuntimeError(f"Failed to generate embedding: {str(e)}")

    def _pull_model(self):
        try:
            from ollama import AsyncClient
            
            async def pull():
                async_client = AsyncClient(host=self.host)
                await async_client.pull(self.model)
            
            import asyncio
            asyncio.run(pull())
            self.model_loaded = True
            logger.info(f"Model {self.model} pulled successfully")
            
        except Exception as e:
            logger.error(f"Failed to pull model: {str(e)}")
            raise RuntimeError(f"Failed to pull model {self.model}: {str(e)}")

    def check_model_status(self) -> Dict[str, Any]:
        if not self.client:
            return {
                'connected': False,
                'model': None,
                'status': 'Client not initialized'
            }
        
        try:
            models = self.client.list()
            model_names = [m['name'] for m in models.get('models', [])]
            
            return {
                'connected': True,
                'model': self.model,
                'model_available': self.model in model_names,
                'available_models': model_names,
                'host': self.host
            }
            
        except Exception as e:
            return {
                'connected': False,
                'model': self.model,
                'error': str(e)
            }

    def is_ready(self) -> bool:
        return self.client is not None

    def unload_model(self):
        if self.client:
            try:
                self.client.generate(
                    model=self.model,
                    prompt='',
                    keep_alive=0
                )
                self.model_loaded = False
                logger.info(f"Model {self.model} unloaded")
            except Exception as e:
                logger.warning(f"Failed to unload model: {str(e)}")

    def get_config(self) -> Dict[str, Any]:
        return {
            'host': self.host,
            'model': self.model,
            'embed_model': self.embed_model,
            'model_loaded': self.model_loaded,
            'last_use_time': self.last_use_time
        }


llm_service = LLMService()
