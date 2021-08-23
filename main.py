import json
import string
import pandas as pd
from zipfile import ZipFile
import sys


class QualtricsConvert:
    instrument_columns = ['Variable / Field Name', 'Form Name', 'Section Header', 'Field Type', 'Field Label', 'Choices, Calculations, OR Slider Labels', 'Field Note', 'Text Validation Type OR Show Slider Number', 'Text Validation Min', 'Text Validation Max', 'Identifier?', 'Branching Logic (Show field only if...)', 'Required Field?', 'Custom Alignment', 'Question Number (surveys only)', 'Matrix Group Name', 'Matrix Ranking?', 'Field Annotation']

    def __init__(self, qsf_file):
        with open(qsf_file) as f:
            self.qsf = json.load(f)

    def find_elements(self, element_type):
        return (el['Payload'] for el in self.qsf['SurveyElements'] if el['Element'] == element_type)

    def find_question(self, qid):
        return next(question for question in self.find_elements('SQ') if question['QuestionID'] == qid)

    @staticmethod
    def read_order(options, order):
        for i, choice_num in enumerate(order):
            choice_text = options[str(choice_num)]['Display']
            yield i, choice_text

    @staticmethod
    def simplify(text):
        chars = []
        for c in text:
            if c in string.ascii_letters:
                chars.append(c.lower())
            elif c in string.digits:
                chars.append(c)
            else:
                chars.append('_')
        return ''.join(chars)

    @staticmethod
    def main():
        converter = QualtricsConvert(sys.argv[1])

        blocks = next(converter.find_elements('BL'))
        if type(blocks) == dict:
            blocks = blocks.values()
        standard_blocks = (block for block in blocks if block['Type'] == 'Standard')

        for block in standard_blocks:
            survey_name = block['Description']
            rows = []

            questions = (element for element in block['BlockElements'] if element['Type'] == 'Question')
            for question in questions:
                qid = question['QuestionID']
                question = converter.find_question(qid)
                qtype = question['QuestionType']
                qtext = question['QuestionText']
                required = 'y' if question['Validation']['Settings'].get('ForceResponse') == 'ON' else None

                if qtype == 'MC':
                    choices = ' | '.join(f'{i}, {text}' for i, text in QualtricsConvert.read_order(question['Choices'], question['ChoiceOrder']))
                    rows.append({
                        'Variable / Field Name': f'{survey_name}_{qid}',
                        'Form Name': survey_name,
                        'Field Type': 'radio',
                        'Field Label': qtext,
                        'Choices, Calculations, OR Slider Labels': choices,
                        'Required Field?': required
                    })
                elif qtype == 'Matrix':
                    answers = ' | '.join(f'{i}, {text}' for i, text in QualtricsConvert.read_order(question['Answers'], question['AnswerOrder']))
                    group_name = f'{survey_name}_{qid}'

                    if question['Selector'] == 'Likert' and question['SubSelector'] == 'SingleAnswer':
                        field_type = 'radio'
                        redcap_matrix = True
                    elif question['Selector'] == 'TE':  # text entry
                        field_type = 'text'
                        redcap_matrix = False
                    else:
                        print(f'warning, unknown selector type {question["Selector"]}, for question id {qid}')
                        continue

                    first = True
                    for i, choice in QualtricsConvert.read_order(question['Choices'], question['ChoiceOrder']):
                        row = {
                            'Variable / Field Name': f'{group_name}_{i}',
                            'Form Name': survey_name,
                            'Field Type': field_type,
                            'Field Label': choice,
                            'Choices, Calculations, OR Slider Labels': answers,
                            'Required Field?': required
                        }
                        if redcap_matrix:
                            row['Matrix Group Name'] = group_name
                        if first:
                            row['Section Header'] = qtext
                            first = False
                        rows.append(row)
                elif qtype == 'TE':
                    # text entry
                    rows.append({
                        'Variable / Field Name': f'{survey_name}_{qid}',
                        'Form Name': survey_name,
                        'Field Type': 'text',
                        'Field Label': qtext,
                        'Required Field?': required
                    })
                elif qtype == 'DB':
                    # descriptive block
                    rows.append({
                        'Variable / Field Name': f'{survey_name}_{qid}',
                        'Form Name': survey_name,
                        'Field Type': 'descriptive',
                        'Field Label': qtext
                    })
                else:
                    print(f'warning, can\'t handle question type {qtype} for question id {qid}')
                    continue

            df = pd.DataFrame(rows, columns=QualtricsConvert.instrument_columns)
            print(f'write zip for {survey_name}')
            with ZipFile(f'out/{survey_name}.zip', 'w') as zipfile:
                with zipfile.open('instrument.csv', 'w') as instruments:
                    df.to_csv(instruments, index=False)


if __name__ == '__main__':
    QualtricsConvert.main()
