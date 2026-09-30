import unittest
from unittest.mock import Mock

from data_berge_core.skills.query import QuerySkill


class RelationalChatScopeTests(unittest.TestCase):
    def test_relational_questions_reach_agent_before_field_shortcut(self):
        for count in (7, 101):
            dataset = {
                "profile": {"relational_schema": {"table_count": count}},
            }
            for question in (
                "Summarize this model. Columns: 1100.\n\nhow many tables in the db",
                "yes but how many table?",
                "Which sheets are available?",
            ):
                with self.subTest(count=count, question=question):
                    skill = QuerySkill.__new__(QuerySkill)
                    skill._answer_with_analyst_plan = Mock(return_value={"answer": "agent result"})
                    history = [{"role": "assistant", "content": "Previously incorrect answer"}]
                    self.assertEqual(skill.answer(question, dataset, history), {"answer": "agent result"})
                    skill._answer_with_analyst_plan.assert_called_once_with(
                        question, dataset, history, data_engineer=None,
                    )
                    self.assertIsNone(skill._answer_dataset_shape_question(question, dataset))

    def test_context_keeps_workbook_and_sql_scope_separate(self):
        skill = QuerySkill.__new__(QuerySkill)
        profile = {
            "row_count": 4, "column_count": 10, "columns": [],
            "relational_schema": {"table_count": 7, "table_names": ["Orders", "Customers"]},
            "source": {"lineage": {"joined_tables": ["Orders"]}},
        }
        context = skill._compact_profile_context(profile)
        self.assertEqual(context["relational_schema"]["table_count"], 7)
        self.assertEqual(context["working_dataset"]["column_count"], 10)
        self.assertEqual(context["working_dataset"]["joined_tables"], ["Orders"])


if __name__ == "__main__":
    unittest.main()
