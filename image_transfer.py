"""
Image Transfer Module for JustIRC
Handles encrypted image chunking and reassembly
"""

import os
from crypto_layer import CryptoLayer

class ImageTransfer:
    """Handles encrypted image transfers"""
    
    CHUNK_SIZE = 32768  # 32KB chunks
    
    def __init__(self, crypto: CryptoLayer):
        self.crypto = crypto
        self.receiving_images = {}  # image_id -> {chunks, metadata}
    
    def prepare_image(self, image_path: str) -> tuple:
        """Read and prepare image for encrypted transfer"""
        with open(image_path, 'rb') as f:
            image_data = f.read()
        
        # Split into chunks
        chunks = []
        for i in range(0, len(image_data), self.CHUNK_SIZE):
            chunks.append(image_data[i:i + self.CHUNK_SIZE])
        
        return chunks, os.path.basename(image_path), len(image_data)
    
    def start_receiving(self, image_id: str, total_chunks: int, metadata: dict):
        """Start receiving an image"""
        self.receiving_images[image_id] = {
            'chunks': [None] * total_chunks,
            'metadata': metadata,
            'received': 0
        }
    
    def add_chunk(self, image_id: str, chunk_number: int, data: bytes):
        """Add a received chunk"""
        if image_id not in self.receiving_images:
            return False
        
        self.receiving_images[image_id]['chunks'][chunk_number] = data
        self.receiving_images[image_id]['received'] += 1
        
        return self.is_complete(image_id)
    
    def is_complete(self, image_id: str) -> bool:
        """Check if image transfer is complete"""
        if image_id not in self.receiving_images:
            return False
        
        img = self.receiving_images[image_id]
        return img['received'] == len(img['chunks'])
    
    def get_complete_image(self, image_id: str) -> tuple:
        """Get completed image data"""
        if not self.is_complete(image_id):
            return None, None
        
        img = self.receiving_images[image_id]
        data = b''.join(img['chunks'])
        metadata = img['metadata']
        
        del self.receiving_images[image_id]
        return data, metadata
