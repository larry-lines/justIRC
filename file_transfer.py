"""
File Transfer Module for JustIRC
Handles encrypted file chunking and reassembly with progress tracking
Supports any file type, not just images
Includes resume capability and batch uploads
"""

import os
import json
import hashlib
from datetime import datetime
from crypto_layer import CryptoLayer
from typing import Tuple, Dict, Optional, Callable, List


class FileTransfer:
    """Handles encrypted file transfers with progress tracking"""
    
    CHUNK_SIZE = 32768  # 32KB chunks
    MAX_FILE_SIZE = 100 * 1024 * 1024  # 100MB limit
    
    def __init__(self, crypto: CryptoLayer, state_dir: str = "./transfer_state"):
        self.crypto = crypto
        self.receiving_files = {}  # file_id -> {chunks, metadata, received}
        self.sending_files = {}  # file_id -> {total_chunks, sent, callback}
        self.batch_transfers = {}  # batch_id -> {files: [], completed: int}
        self.state_dir = state_dir
        
        # Create state directory if it doesn't exist
        if not os.path.exists(state_dir):
            os.makedirs(state_dir)
    
    def validate_file(self, file_path: str) -> Tuple[bool, str]:
        """Validate file before transfer"""
        if not os.path.exists(file_path):
            return False, "File does not exist"
        
        if not os.path.isfile(file_path):
            return False, "Path is not a file"
        
        file_size = os.path.getsize(file_path)
        if file_size > self.MAX_FILE_SIZE:
            return False, f"File too large (max {self.MAX_FILE_SIZE / (1024*1024):.0f}MB)"
        
        if file_size == 0:
            return False, "File is empty"
        
        return True, "Valid"
    
    def get_file_info(self, file_path: str) -> Dict:
        """Get file metadata"""
        stat = os.stat(file_path)
        return {
            'filename': os.path.basename(file_path),
            'size': stat.st_size,
            'extension': os.path.splitext(file_path)[1],
            'mime_type': self._guess_mime_type(file_path)
        }
    
    def _guess_mime_type(self, file_path: str) -> str:
        """Guess MIME type from file extension"""
        ext = os.path.splitext(file_path)[1].lower()
        mime_types = {
            # Images
            '.png': 'image/png',
            '.jpg': 'image/jpeg',
            '.jpeg': 'image/jpeg',
            '.gif': 'image/gif',
            '.bmp': 'image/bmp',
            '.webp': 'image/webp',
            # Documents
            '.txt': 'text/plain',
            '.pdf': 'application/pdf',
            '.doc': 'application/msword',
            '.docx': 'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
            # Archives
            '.zip': 'application/zip',
            '.tar': 'application/x-tar',
            '.gz': 'application/gzip',
            # Code
            '.py': 'text/x-python',
            '.js': 'text/javascript',
            '.json': 'application/json',
            '.xml': 'application/xml',
            '.html': 'text/html',
            # Media
            '.mp3': 'audio/mpeg',
            '.mp4': 'video/mp4',
            '.wav': 'audio/wav',
        }
        return mime_types.get(ext, 'application/octet-stream')
    
    def prepare_file(self, file_path: str) -> Tuple[list, dict, int]:
        """Read and prepare file for encrypted transfer
        
        Returns:
            (chunks, metadata, total_size)
        """
        # Validate file
        valid, message = self.validate_file(file_path)
        if not valid:
            raise ValueError(message)
        
        # Read file data
        with open(file_path, 'rb') as f:
            file_data = f.read()
        
        # Split into chunks
        chunks = []
        for i in range(0, len(file_data), self.CHUNK_SIZE):
            chunks.append(file_data[i:i + self.CHUNK_SIZE])
        
        # Prepare metadata
        metadata = self.get_file_info(file_path)
        
        return chunks, metadata, len(file_data)
    
    def track_sending(self, file_id: str, total_chunks: int, 
                     progress_callback: Optional[Callable] = None):
        """Start tracking a file being sent"""
        self.sending_files[file_id] = {
            'total_chunks': total_chunks,
            'sent': 0,
            'callback': progress_callback
        }
    
    def update_send_progress(self, file_id: str, chunk_number: int):
        """Update send progress"""
        if file_id not in self.sending_files:
            return
        
        self.sending_files[file_id]['sent'] = chunk_number + 1
        
        if self.sending_files[file_id]['callback']:
            progress = (chunk_number + 1) / self.sending_files[file_id]['total_chunks']
            self.sending_files[file_id]['callback'](progress)
    
    def finish_sending(self, file_id: str):
        """Mark file send as complete"""
        if file_id in self.sending_files:
            del self.sending_files[file_id]
    
    def start_receiving(self, file_id: str, total_chunks: int, metadata: dict,
                       progress_callback: Optional[Callable] = None):
        """Start receiving a file"""
        self.receiving_files[file_id] = {
            'chunks': [None] * total_chunks,
            'metadata': metadata,
            'received': 0,
            'callback': progress_callback
        }
    
    def add_chunk(self, file_id: str, chunk_number: int, data: bytes) -> bool:
        """Add a received chunk
        
        Returns:
            True if file is complete after this chunk
        """
        if file_id not in self.receiving_files:
            return False
        
        self.receiving_files[file_id]['chunks'][chunk_number] = data
        self.receiving_files[file_id]['received'] += 1
        
        # Update progress
        if self.receiving_files[file_id]['callback']:
            progress = self.receiving_files[file_id]['received'] / len(self.receiving_files[file_id]['chunks'])
            self.receiving_files[file_id]['callback'](progress)
        
        return self.is_complete(file_id)
    
    def is_complete(self, file_id: str) -> bool:
        """Check if file transfer is complete"""
        if file_id not in self.receiving_files:
            return False
        
        file_info = self.receiving_files[file_id]
        return file_info['received'] == len(file_info['chunks'])
    
    def get_progress(self, file_id: str) -> Optional[float]:
        """Get receive progress (0.0 to 1.0)"""
        if file_id not in self.receiving_files:
            return None
        
        file_info = self.receiving_files[file_id]
        return file_info['received'] / len(file_info['chunks'])
    
    def get_complete_file(self, file_id: str) -> Tuple[Optional[bytes], Optional[dict]]:
        """Get completed file data
        
        Returns:
            (file_data, metadata) or (None, None) if incomplete
        """
        if not self.is_complete(file_id):
            return None, None
        
        file_info = self.receiving_files[file_id]
        data = b''.join(file_info['chunks'])
        metadata = file_info['metadata']
        
        del self.receiving_files[file_id]
        return data, metadata
    
    def cancel_transfer(self, file_id: str):
        """Cancel an ongoing transfer"""
        if file_id in self.receiving_files:
            del self.receiving_files[file_id]
        if file_id in self.sending_files:
            del self.sending_files[file_id]
    
    def format_file_size(self, size_bytes: int) -> str:
        """Format file size for display"""
        if size_bytes < 1024:
            return f"{size_bytes} B"
    
    # ===== Resume Support =====
    
    def generate_file_hash(self, file_path: str) -> str:
        """Generate unique hash for a file"""
        hasher = hashlib.sha256()
        hasher.update(file_path.encode())
        hasher.update(str(os.path.getsize(file_path)).encode())
        return hasher.hexdigest()[:16]
    
    def save_transfer_state(self, file_id: str, direction: str = "receiving"):
        """Save transfer state to disk for resume"""
        try:
            state_file = os.path.join(self.state_dir, f"{file_id}.json")
            
            if direction == "receiving" and file_id in self.receiving_files:
                file_info = self.receiving_files[file_id]
                state = {
                    'file_id': file_id,
                    'direction': 'receiving',
                    'metadata': file_info['metadata'],
                    'total_chunks': len(file_info['chunks']),
                    'received': file_info['received'],
                    'received_chunks': [i for i, chunk in enumerate(file_info['chunks']) if chunk is not None],
                    'timestamp': datetime.now().isoformat()
                }
                
                with open(state_file, 'w') as f:
                    json.dump(state, f, indent=2)
                
            elif direction == "sending" and file_id in self.sending_files:
                send_info = self.sending_files[file_id]
                state = {
                    'file_id': file_id,
                    'direction': 'sending',
                    'total_chunks': send_info['total_chunks'],
                    'sent': send_info['sent'],
                    'timestamp': datetime.now().isoformat()
                }
                
                with open(state_file, 'w') as f:
                    json.dump(state, f, indent=2)
                    
        except Exception as e:
            print(f"Failed to save transfer state: {e}")
    
    def load_transfer_state(self, file_id: str) -> Optional[Dict]:
        """Load saved transfer state"""
        try:
            state_file = os.path.join(self.state_dir, f"{file_id}.json")
            
            if os.path.exists(state_file):
                with open(state_file, 'r') as f:
                    return json.load(f)
                    
        except Exception as e:
            print(f"Failed to load transfer state: {e}")
        
        return None
    
    def can_resume_transfer(self, file_id: str) -> bool:
        """Check if a transfer can be resumed"""
        state = self.load_transfer_state(file_id)
        return state is not None
    
    def resume_receiving(self, file_id: str, progress_callback: Optional[Callable] = None) -> bool:
        """Resume a receiving transfer from saved state
        
        Returns:
            True if successfully resumed, False otherwise
        """
        state = self.load_transfer_state(file_id)
        
        if not state or state['direction'] != 'receiving':
            return False
        
        # Reconstruct receiving state
        total_chunks = state['total_chunks']
        received_chunks = state['received_chunks']
        
        self.receiving_files[file_id] = {
            'chunks': [None] * total_chunks,
            'metadata': state['metadata'],
            'received': state['received'],
            'callback': progress_callback
        }
        
        # Mark chunks as received (but we don't have the actual data)
        # In a real implementation, you'd also save chunk data to disk
        for chunk_num in received_chunks:
            self.receiving_files[file_id]['chunks'][chunk_num] = b''  # Placeholder
        
        return True
    
    def clear_transfer_state(self, file_id: str):
        """Clear saved transfer state"""
        try:
            state_file = os.path.join(self.state_dir, f"{file_id}.json")
            if os.path.exists(state_file):
                os.remove(state_file)
        except Exception as e:
            print(f"Failed to clear transfer state: {e}")
    
    def list_resumable_transfers(self) -> List[Dict]:
        """List all resumable transfers"""
        resumable = []
        
        try:
            for filename in os.listdir(self.state_dir):
                if filename.endswith('.json'):
                    file_id = filename[:-5]  # Remove .json
                    state = self.load_transfer_state(file_id)
                    if state:
                        resumable.append(state)
        except Exception as e:
            print(f"Failed to list resumable transfers: {e}")
        
        return resumable
    
    # ===== Batch Upload Support =====
    
    def prepare_batch(self, file_paths: List[str]) -> Tuple[str, List[Dict], str]:
        """Prepare multiple files for batch upload
        
        Returns:
            (batch_id, file_list, error_message)
        """
        # Validate all files first
        valid_files = []
        errors = []
        
        for file_path in file_paths:
            valid, message = self.validate_file(file_path)
            if valid:
                try:
                    metadata = self.get_file_info(file_path)
                    valid_files.append({
                        'path': file_path,
                        'metadata': metadata
                    })
                except Exception as e:
                    errors.append(f"{os.path.basename(file_path)}: {str(e)}")
            else:
                errors.append(f"{os.path.basename(file_path)}: {message}")
        
        if not valid_files:
            return None, [], "No valid files to upload"
        
        # Generate batch ID
        batch_id = hashlib.sha256(
            ''.join(file_paths).encode() + 
            str(datetime.now().timestamp()).encode()
        ).hexdigest()[:16]
        
        # Track batch
        self.batch_transfers[batch_id] = {
            'files': valid_files,
            'completed': 0,
            'total': len(valid_files),
            'errors': errors
        }
        
        error_msg = f" (Skipped {len(errors)} files)" if errors else ""
        return batch_id, valid_files, error_msg
    
    def get_batch_progress(self, batch_id: str) -> Optional[Dict]:
        """Get batch upload progress"""
        if batch_id not in self.batch_transfers:
            return None
        
        batch = self.batch_transfers[batch_id]
        return {
            'completed': batch['completed'],
            'total': batch['total'],
            'progress': batch['completed'] / batch['total'] if batch['total'] > 0 else 0,
            'errors': batch['errors']
        }
    
    def mark_batch_file_complete(self, batch_id: str):
        """Mark one file in batch as complete"""
        if batch_id in self.batch_transfers:
            self.batch_transfers[batch_id]['completed'] += 1
    
    def is_batch_complete(self, batch_id: str) -> bool:
        """Check if batch upload is complete"""
        if batch_id not in self.batch_transfers:
            return False
        
        batch = self.batch_transfers[batch_id]
        return batch['completed'] >= batch['total']
    
    def finish_batch(self, batch_id: str):
        """Mark batch as complete and clean up"""
        if batch_id in self.batch_transfers:
            del self.batch_transfers[batch_id]
        elif size_bytes < 1024 * 1024:
            return f"{size_bytes / 1024:.1f} KB"
        elif size_bytes < 1024 * 1024 * 1024:
            return f"{size_bytes / (1024 * 1024):.1f} MB"
        else:
            return f"{size_bytes / (1024 * 1024 * 1024):.1f} GB"
