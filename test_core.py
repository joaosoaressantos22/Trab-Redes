import unittest
import asyncio
from unittest.mock import AsyncMock, MagicMock, patch
from http_parser import HttpProtocolHandler
from matrix_client import BareMetalAsyncClient
from exceptions import HTTPParsingError, MatrixAPIError

class TestProtocolParser(unittest.IsolatedAsyncioTestCase):
    
    async def test_parse_response_content_length(self):
        reader_mock = AsyncMock()
        payload = b"HTTP/1.1 200 OK\r\nContent-Length: 13\r\n\r\nHello Matrix!"
        reader_mock.read.side_effect = [payload, b"", b""]
        
        status, headers, body = await HttpProtocolHandler.parse_response(reader_mock)
        self.assertEqual(status, 200)
        self.assertEqual(body, b"Hello Matrix!")

    async def test_parse_response_chunked(self):
        reader_mock = AsyncMock()
        payload_chunks = [
            b"HTTP/1.1 200 OK\r\nTransfer-Encoding: chunked\r\n\r\n",
            b"4\r\nWiki\r\n",
            b"5\r\npedia\r\n",
            b"E\r\n in\r\n\r\nchunks.\r\n",
            b"0\r\n\r\n"
        ]
        reader_mock.read.side_effect = payload_chunks + [b"", b"", b""]
        
        status, headers, body = await HttpProtocolHandler.parse_response(reader_mock)
        self.assertEqual(status, 200)
        self.assertEqual(body, b"Wikipedia in\r\n\r\nchunks.")

    async def test_eof_handling(self):
        reader_mock = AsyncMock()
        reader_mock.read.return_value = b"" 
        
        with self.assertRaises(HTTPParsingError):
            await HttpProtocolHandler.parse_response(reader_mock)

class TestMatrixClient(unittest.IsolatedAsyncioTestCase):

    async def test_api_error_handling(self):
        client = BareMetalAsyncClient("localhost:8008")
        
        # Correção do payload e sincronização do cabeçalho Content-Length
        error_json = b'{"errcode":"M_FORBIDDEN","error":"No"}' # 38 bytes
        content_length = len(error_json) # 38
        
        headers = f"HTTP/1.1 403 Forbidden\r\nContent-Length: {content_length}\r\n\r\n".encode('utf-8')
        
        reader_mock = AsyncMock()
        reader_mock.read.side_effect = [
            headers + error_json,
            b"", b""
        ]
        
        writer_mock = MagicMock()
        writer_mock.write = MagicMock()
        writer_mock.drain = AsyncMock()
        writer_mock.close = MagicMock()
        writer_mock.wait_closed = AsyncMock()
        
        with patch('asyncio.open_connection', AsyncMock(return_value=(reader_mock, writer_mock))):
            with self.assertRaises(MatrixAPIError) as contexto:
                await client.login("teste", "senha")
            
            self.assertEqual(contexto.exception.status_code, 403)
            self.assertEqual(contexto.exception.payload["errcode"], "M_FORBIDDEN")

if __name__ == '__main__':
    unittest.main()