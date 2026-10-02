"""Standalone, network-free demonstration of typed lesson retrieval."""
import json
import re

from verantyx.memory_lessons import LessonIndex


def main():
    connection_lesson = {
        'id': 'lesson-connection',
        'kind': 'LESSON',
        'slots': {
            'situation': 'internet outage',
            'fix': 'Check the modem power and service status.',
        },
    }
    password_lesson = {
        'id': 'lesson-password',
        'kind': 'LESSON',
        'slots': {
            'situation': 'password reset',
            'fix': 'Use the approved account recovery process.',
        },
    }
    records = [connection_lesson, password_lesson]

    exact_index = LessonIndex(records)
    assert exact_index.lessons_for('internet outage') == [connection_lesson]
    assert exact_index.testimonies == []

    prompts = []

    def closed_asker(prompt):
        prompts.append(prompt)
        options = re.findall(r'(?m)^\d+: (.*)$', prompt)
        return json.dumps({'choice': options.index('internet outage')})

    index = LessonIndex(records, asker=closed_asker)
    selected = index.lessons_for('connection unavailable')
    assert selected == [connection_lesson]
    assert len(prompts) == 2
    assert prompts[0] != prompts[1]
    assert index.testimonies[0]['kind'] == 'TESTIMONY'
    assert index.testimonies[0]['status'] == 'ADOPT'
    assert index.testimonies[0]['choice'] == 'internet outage'
    combined_prompt = '\n'.join(prompts)
    assert 'lesson-connection' not in combined_prompt
    assert connection_lesson['slots']['fix'] not in combined_prompt
    assert password_lesson['slots']['fix'] not in combined_prompt

    print('DEMO OK')


if __name__ == '__main__':
    main()
