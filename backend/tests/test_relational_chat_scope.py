import unittest
from unittest.mock import Mock

from data_berge_core.skills.query import QuerySkill


class RelationalChatScopeTests(unittest.TestCase):
    def test_unavailable_planner_answers_only_unambiguous_metadata(self):
        dataset = {
            "name": "stress test", "row_count": 4, "column_count": 10,
            "profile": {
                "row_count": 4, "column_count": 10,
                "relational_schema": {"table_count": 101},
                "source": {"lineage": {"joined_tables": ["Table 001"]}},
            },
        }
        skill = QuerySkill.__new__(QuerySkill)
        skill.planner_agent = object()
        for question in ("how many tables in the dataset", "how many tables in the db?"):
            with self.subTest(question=question):
                response = skill.answer(question, dataset)
                self.assertEqual(response["answer"], "The workbook contains 101 tables.")
                self.assertIsNone(response["sql"])
        overview = skill.answer("what is the dataset is about?", dataset)
        self.assertIn("101 tables", overview["answer"])
        self.assertIn("4 rows and 10 columns", overview["answer"])
        self.assertIn("Table 001", overview["answer"])
        for question in ("how many tables contain missing values?", "why?", "how many rows in Table 002?"):
            with self.subTest(question=question):
                response = skill.answer(question, dataset)
                self.assertEqual(response["confidence"], 0.0)
                self.assertIn("analysis service", response["answer"])

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
