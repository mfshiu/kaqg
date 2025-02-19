import unittest

# Function to be tested
_facts = {}

def _is_subject_exist(session, subject_type, subject_name, file_id, page_number):
    global _facts

    if file_id not in _facts:
        _facts[file_id] = []

    file_facts = _facts.get(file_id, [])
    if (fflen := len(file_facts)) <= page_number:
        new_size = max(page_number+1, max(10, fflen*2))
        for _ in range(new_size - fflen):
            file_facts.append(set())
        print(f"Extended list to {new_size} items, real size: {len(file_facts)}.")

    key = f"{subject_type}-{subject_name}"
    is_existing = key in file_facts[page_number]

    if not is_existing:
        file_facts[page_number].add(key)

    return is_existing


# Test cases
class TestIsSubjectExist(unittest.TestCase):

    def setUp(self):
        global _facts
        _facts.clear()  # Reset before each test


    def test_subject_not_exist(self):
        """Test that a new subject does not exist initially."""
        session = None
        result = _is_subject_exist(session, "Person", "Alice", "file1", 2)
        self.assertFalse(result)  # Should return False


    def test_subject_added(self):
        """Test that once a subject is checked, it is marked as existing."""
        session = None
        _is_subject_exist(session, "Person", "Alice", "file1", 2)
        result = _is_subject_exist(session, "Person", "Alice", "file1", 2)
        self.assertTrue(result)  # Should return True


    def test_different_subjects(self):
        """Test that different subjects are stored separately."""
        session = None
        _is_subject_exist(session, "Person", "Alice", "file1", 2)
        result = _is_subject_exist(session, "Person", "Bob", "file1", 2)
        self.assertFalse(result)  # Should return False


    def test_different_files(self):
        """Test that subjects are tracked per file_id separately."""
        session = None
        _is_subject_exist(session, "Person", "Alice", "file1", 2)
        result = _is_subject_exist(session, "Person", "Alice", "file2", 2)
        self.assertFalse(result)  # Should return False


    def test_different_pages(self):
        """Test that subjects are tracked per page_number separately."""
        session = None
        _is_subject_exist(session, "Person", "Alice", "file1", 2)
        result = _is_subject_exist(session, "Person", "Alice", "file1", 3)
        self.assertFalse(result)  # Should return False


    def test_extend_list(self):
        """Test that the list is extended properly when page_number is large."""
        session = None
        _is_subject_exist(session, "Person", "Alice", "file1", 15)
        result = _is_subject_exist(session, "Person", "Alice", "file1", 15)
        self.assertTrue(result)  # Should return True after adding


    def test_large_index(self):
        """Test handling of a very large page number."""
        session = None
        _is_subject_exist(session, "Person", "Charlie", "file3", 1000)
        result = _is_subject_exist(session, "Person", "Charlie", "file3", 1000)
        self.assertTrue(result)  # Should return True


if __name__ == '__main__':
    unittest.main()
