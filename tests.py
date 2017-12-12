from unittest.case import TestCase
from main import DeletionJob


class DeletionJobTestCase(TestCase):
    def test_run(self):
        hasattr(DeletionJob, 'run')