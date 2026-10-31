import sys
import unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1] / "scripts"))
import safe_runtime
import operation_policy
class PerAccountMembershipTests(unittest.TestCase):
    def test_same_group_belongs_to_each_account_independently(self):
        state=operation_policy.empty_state()
        state["joined_groups"]["1:@publicgroup"]={"account":1}
        self.assertIsNotNone(safe_runtime.group_record(state,"joined_groups",1,"@publicgroup"))
        self.assertIsNone(safe_runtime.group_record(state,"joined_groups",2,"@publicgroup"))
        state["joined_groups"]["2:@publicgroup"]={"account":2}
        self.assertIsNotNone(safe_runtime.group_record(state,"joined_groups",2,"@publicgroup"))
    def test_legacy_group_record_does_not_block_other_account(self):
        state=operation_policy.empty_state()
        state["pending_group_actions"]["@publicgroup"]={"account":1}
        self.assertIsNotNone(safe_runtime.group_record(state,"pending_group_actions",1,"@publicgroup"))
        self.assertIsNone(safe_runtime.group_record(state,"pending_group_actions",2,"@publicgroup"))
    def test_account_case_insensitive_keys(self):
        self.assertEqual(safe_runtime.group_action_key(1,"@SomeGroup"),"1:@somegroup")
        self.assertEqual(safe_runtime.group_action_key(2,"@somegroup"),"2:@somegroup")
