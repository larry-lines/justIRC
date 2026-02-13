"""
Tests for Enhanced File Transfer (Resume & Batch)
"""

import unittest
import os
import sys
import tempfile
import shutil

# Add parent directory to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from file_transfer import FileTransfer
from crypto_layer import CryptoLayer


class TestFileTransferEnhancements(unittest.TestCase):
    """Test file transfer resume and batch features"""
    
    def setUp(self):
        """Set up crypto and file transfer"""
        self.crypto = CryptoLayer()
        
        # Create temp directories
        self.temp_dir = tempfile.mkdtemp()
        self.state_dir = tempfile.mkdtemp()
        
        self.file_transfer = FileTransfer(self.crypto, state_dir=self.state_dir)
        
        # Create test files
        self.test_file1 = os.path.join(self.temp_dir, 'test1.txt')
        self.test_file2 = os.path.join(self.temp_dir, 'test2.txt')
        self.test_file3 = os.path.join(self.temp_dir, 'test3.txt')
        
        with open(self.test_file1, 'w') as f:
            f.write('Test file 1 content')
        with open(self.test_file2, 'w') as f:
            f.write('Test file 2 content')
        with open(self.test_file3, 'w') as f:
            f.write('Test file 3 content')
    
    def tearDown(self):
        """Clean up temp directories"""
        shutil.rmtree(self.temp_dir)
        shutil.rmtree(self.state_dir)
    
    # ===== Resume Tests =====
    
    def test_generate_file_hash(self):
        """Test file hash generation"""
        hash1 = self.file_transfer.generate_file_hash(self.test_file1)
        hash2 = self.file_transfer.generate_file_hash(self.test_file1)
        hash3 = self.file_transfer.generate_file_hash(self.test_file2)
        
        # Same file should produce same hash
        self.assertEqual(hash1, hash2)
        
        # Different files should produce different hashes
        self.assertNotEqual(hash1, hash3)
        
        # Hash should be 16 chars
        self.assertEqual(len(hash1), 16)
    
    def test_save_and_load_transfer_state_receiving(self):
        """Test saving and loading receiving transfer state"""
        file_id = 'test_file_123'
        
        # Start a receiving transfer
        self.file_transfer.start_receiving(file_id, 5, {'filename': 'test.txt', 'size': 1000})
        
        # Add some chunks
        self.file_transfer.add_chunk(file_id, 0, b'chunk0')
        self.file_transfer.add_chunk(file_id, 1, b'chunk1')
        
        # Save state
        self.file_transfer.save_transfer_state(file_id, 'receiving')
        
        # Load state
        state = self.file_transfer.load_transfer_state(file_id)
        
        self.assertIsNotNone(state)
        self.assertEqual(state['direction'], 'receiving')
        self.assertEqual(state['total_chunks'], 5)
        self.assertEqual(state['received'], 2)
        self.assertEqual(len(state['received_chunks']), 2)
    
    def test_save_and_load_transfer_state_sending(self):
        """Test saving and loading sending transfer state"""
        file_id = 'test_file_456'
        
        # Start tracking a send
        self.file_transfer.track_sending(file_id, 10)
        
        # Update progress
        self.file_transfer.update_send_progress(file_id, 3)
        
        # Save state
        self.file_transfer.save_transfer_state(file_id, 'sending')
        
        # Load state
        state = self.file_transfer.load_transfer_state(file_id)
        
        self.assertIsNotNone(state)
        self.assertEqual(state['direction'], 'sending')
        self.assertEqual(state['total_chunks'], 10)
        self.assertEqual(state['sent'], 4)  # 0-indexed, so chunk 3 = 4 sent
    
    def test_can_resume_transfer(self):
        """Test checking if transfer can be resumed"""
        file_id = 'test_file_789'
        
        # Non-existent transfer
        self.assertFalse(self.file_transfer.can_resume_transfer(file_id))
        
        # Save a transfer state
        self.file_transfer.start_receiving(file_id, 3, {'filename': 'test.txt'})
        self.file_transfer.save_transfer_state(file_id, 'receiving')
        
        # Should be able to resume
        self.assertTrue(self.file_transfer.can_resume_transfer(file_id))
    
    def test_resume_receiving(self):
        """Test resuming a receiving transfer"""
        file_id = 'test_resume'
        
        # Start and partially complete a transfer
        self.file_transfer.start_receiving(file_id, 4, {'filename': 'test.txt', 'size': 800})
        self.file_transfer.add_chunk(file_id, 0, b'chunk0')
        self.file_transfer.add_chunk(file_id, 1, b'chunk1')
        self.file_transfer.save_transfer_state(file_id, 'receiving')
        
        # Simulate disconnection
        del self.file_transfer.receiving_files[file_id]
        
        # Resume
        success = self.file_transfer.resume_receiving(file_id)
        self.assertTrue(success)
        
        # Should be in receiving_files again
        self.assertIn(file_id, self.file_transfer.receiving_files)
        
        # Should have correct metadata
        self.assertEqual(
            self.file_transfer.receiving_files[file_id]['metadata']['filename'],
            'test.txt'
        )
    
    def test_clear_transfer_state(self):
        """Test clearing transfer state"""
        file_id = 'test_clear'
        
        self.file_transfer.start_receiving(file_id, 2, {'filename': 'test.txt'})
        self.file_transfer.save_transfer_state(file_id, 'receiving')
        
        # State should exist
        self.assertTrue(self.file_transfer.can_resume_transfer(file_id))
        
        # Clear it
        self.file_transfer.clear_transfer_state(file_id)
        
        # State should be gone
        self.assertFalse(self.file_transfer.can_resume_transfer(file_id))
    
    def test_list_resumable_transfers(self):
        """Test listing all resumable transfers"""
        # Create multiple transfer states
        for i in range(3):
            file_id = f'test_file_{i}'
            self.file_transfer.start_receiving(file_id, 2, {'filename': f'test{i}.txt'})
            self.file_transfer.save_transfer_state(file_id, 'receiving')
        
        # List resumable
        resumable = self.file_transfer.list_resumable_transfers()
        
        self.assertEqual(len(resumable), 3)
        file_ids = [state['file_id'] for state in resumable]
        self.assertIn('test_file_0', file_ids)
        self.assertIn('test_file_1', file_ids)
        self.assertIn('test_file_2', file_ids)
    
    # ===== Batch Upload Tests =====
    
    def test_prepare_batch_success(self):
        """Test preparing a batch of valid files"""
        file_paths = [self.test_file1, self.test_file2, self.test_file3]
        
        batch_id, files, error_msg = self.file_transfer.prepare_batch(file_paths)
        
        self.assertIsNotNone(batch_id)
        self.assertEqual(len(files), 3)
        self.assertEqual(error_msg, '')
        self.assertIn(batch_id, self.file_transfer.batch_transfers)
    
    def test_prepare_batch_with_invalid_files(self):
        """Test preparing a batch with some invalid files"""
        invalid_file = os.path.join(self.temp_dir, 'nonexistent.txt')
        file_paths = [self.test_file1, invalid_file, self.test_file2]
        
        batch_id, files, error_msg = self.file_transfer.prepare_batch(file_paths)
        
        self.assertIsNotNone(batch_id)
        self.assertEqual(len(files), 2)  # Only valid files
        self.assertIn('Skipped', error_msg)
    
    def test_prepare_batch_no_valid_files(self):
        """Test preparing a batch with no valid files"""
        invalid_files = [
            os.path.join(self.temp_dir, 'fake1.txt'),
            os.path.join(self.temp_dir, 'fake2.txt')
        ]
        
        batch_id, files, error_msg = self.file_transfer.prepare_batch(invalid_files)
        
        self.assertIsNone(batch_id)
        self.assertEqual(len(files), 0)
        self.assertIn('No valid files', error_msg)
    
    def test_get_batch_progress(self):
        """Test getting batch upload progress"""
        file_paths = [self.test_file1, self.test_file2, self.test_file3]
        batch_id, _, _ = self.file_transfer.prepare_batch(file_paths)
        
        # Initial progress
        progress = self.file_transfer.get_batch_progress(batch_id)
        self.assertEqual(progress['completed'], 0)
        self.assertEqual(progress['total'], 3)
        self.assertEqual(progress['progress'], 0.0)
        
        # Mark one complete
        self.file_transfer.mark_batch_file_complete(batch_id)
        progress = self.file_transfer.get_batch_progress(batch_id)
        self.assertEqual(progress['completed'], 1)
        self.assertAlmostEqual(progress['progress'], 1/3)
        
        # Mark another complete
        self.file_transfer.mark_batch_file_complete(batch_id)
        progress = self.file_transfer.get_batch_progress(batch_id)
        self.assertEqual(progress['completed'], 2)
        self.assertAlmostEqual(progress['progress'], 2/3)
    
    def test_get_batch_progress_nonexistent(self):
        """Test getting progress for non-existent batch"""
        progress = self.file_transfer.get_batch_progress('fake_batch_id')
        self.assertIsNone(progress)
    
    def test_is_batch_complete(self):
        """Test checking if batch is complete"""
        file_paths = [self.test_file1, self.test_file2]
        batch_id, _, _ = self.file_transfer.prepare_batch(file_paths)
        
        # Not complete yet
        self.assertFalse(self.file_transfer.is_batch_complete(batch_id))
        
        # Mark files complete
        self.file_transfer.mark_batch_file_complete(batch_id)
        self.assertFalse(self.file_transfer.is_batch_complete(batch_id))
        
        self.file_transfer.mark_batch_file_complete(batch_id)
        self.assertTrue(self.file_transfer.is_batch_complete(batch_id))
    
    def test_finish_batch(self):
        """Test finishing a batch"""
        file_paths = [self.test_file1]
        batch_id, _, _ = self.file_transfer.prepare_batch(file_paths)
        
        # Batch should exist
        self.assertIn(batch_id, self.file_transfer.batch_transfers)
        
        # Finish it
        self.file_transfer.finish_batch(batch_id)
        
        # Batch should be gone
        self.assertNotIn(batch_id, self.file_transfer.batch_transfers)
    
    def test_batch_id_uniqueness(self):
        """Test that batch IDs are unique"""
        file_paths = [self.test_file1]
        
        batch_id1, _, _ = self.file_transfer.prepare_batch(file_paths)
        batch_id2, _, _ = self.file_transfer.prepare_batch(file_paths)
        
        self.assertNotEqual(batch_id1, batch_id2)


if __name__ == '__main__':
    unittest.main()
