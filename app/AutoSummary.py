import sqlite3 as sqllite
import sys

from flask import Flask, jsonify, request

from sumy.parsers.plaintext import PlaintextParser
from sumy.nlp.tokenizers import Tokenizer
from sumy.summarizers.text_rank import TextRankSummarizer
from sumy.summarizers.luhn import LuhnSummarizer
from sumy.summarizers.edmundson import EdmundsonSummarizer
from sumy.summarizers.kl import KLSummarizer
from sumy.summarizers.lex_rank import LexRankSummarizer
from sumy.summarizers.lsa import LsaSummarizer
from sumy.summarizers.sum_basic import SumBasicSummarizer
from sumy.summarizers.random import RandomSummarizer

from sumy.nlp.stemmers import Stemmer
from sumy.utils import get_stop_words

from flask_restplus import Api, Resource, fields, marshal, abort


class ReviewDAL:

    con = None
    cur = None

    def __init__(self):
        self.setup_sql_lite_db()

    def setup_sql_lite_db(self):
        try:

            self.con = sqllite.connect('reviews.db')
            self.cur = self.con.cursor()
            #cur.execute('DROP TABLE IF EXISTS Comment')
            sql = "CREATE TABLE IF NOT EXISTS Review (" \
                  "    id INTEGER PRIMARY KEY AUTOINCREMENT, " \
                  "    assignment_id VARCHAR, " \
                  "    criterion_id VARCHAR, " \
                  "    reviewer_id VARCHAR, " \
                  "    reviewee_id VARCHAR, " \
                  "    score VARCHAR, " \
                  "    feedback VARCHAR)"
            self.cur.execute(sql)
            self.con.commit()

        except sqllite.Error, e:
            print "Error %s:" % e.args[0]
            sys.exit(1)


    def insert_tuples(self, tuples):
        self.cur.executemany("INSERT INTO Review VALUES(NULL, ?, ?, ?, ?, ?, ?)", tuples)
        self.con.commit()


    def insert_reviews(self, assignment_id, criterion_id, reviewer_id, reviewee_id, score, feedback):
        if assignment_id.isdigit and criterion_id.isdigit and reviewer_id.isdigit and reviewee_id.isdigit :
            self.cur.execute("INSERT INTO Review VALUES(NULL, " + str(assignment_id) + ", " + str(criterion_id) + ", " + str(reviewer_id) + ", " +  str(reviewee_id) + "," +  str(score) + ", \'" +feedback + "\')")
        else:
            raise ValueError("All IDs must be number and greater than zero")

    def commit(self):
        self.con.commit()

    def is_record_exist(self, assignment_id, criterion_id=-1, reviewee_id=-1):

        if (criterion_id == -1 and reviewee_id == -1):
            raise Exception("criterion_id & reviewee_id cannot be both empty nor negative")

        if(reviewee_id == -1):
            result = self.get_reviews_by_assignment_criterion(assignment_id, criterion_id)
            return True if len(result)>0 else False
        elif (criterion_id == -1):
            result = self.get_reviews_by_assignment_reviewee(self, assignment_id, reviewee_id)
            return True if result.count()>0 else False
        else:
            result = self.get_reviews_by_assignment_criterion_reviewee(self, assignment_id, criterion_id, reviewee_id)
            return True if result.count()>0 else False


    def get_reviews_by_assignment_criterion(self, assignment_id, criterion_id):

        str_query='SELECT reviewer_id, reviewee_id, score, feedback ' \
                  'FROM Review ' \
                  'WHERE assignment_id= ' + assignment_id + ' AND criterion_id= ' + criterion_id + ' ' \
                  'ORDER BY reviewee_id'
        self.cur.execute(str_query)
        rows = self.cur.fetchall()
        return [{"reviewer_id":str(item[0]), "reviewee_id":str(item[1]), "score":str(item[2]), "feedback":str(item[3])} for item in rows]

    def del_reviews_by_assignment_criterion(self, assignment_id, criterion_id):

        str_query='DELETE FROM Review ' \
                  'WHERE assignment_id= ' + assignment_id + ' AND criterion_id= ' + criterion_id
        self.cur.execute(str_query)



    def get_reviews_by_assignment_reviewee(self, assignment_id, reviewee_id):

        str_query='SELECT reviewer_id, criterion_id, score, feedback ' \
                  'FROM Review ' \
                  'WHERE assignment_id= ' + assignment_id + ' AND reviewee = ' + reviewee_id + ' ' \
                  'ORDER BY score'
        self.cur.execute(str_query)
        row = self.cur.fetchall()
        return row

    def del_reviews_by_assignment_reviewee(self, assignment_id, reviewee_id):

        str_query='DELETE FROM Review ' \
                  'WHERE assignment_id= ' + assignment_id + ' AND reviewee = ' + reviewee_id
        self.cur.execute(str_query)


    def get_reviews_by_assignment_criterion_reviewee(self, assignment_id, reviewee_id, criterion_id ):

        str_query='SELECT reviewer_id, score, feedback ' \
                  'FROM Review ' \
                  'WHERE assignment_id= ' + assignment_id + ' AND criterion_id= ' + criterion_id + ' AND reviewee = ' + reviewee_id + ' ' \
                  'ORDER BY score'
        self.cur.execute(str_query)
        return self.cur.fetchall()

    def del_reviews_by_assignment_criterion_reviewee(self, assignment_id, reviewee_id, criterion_id,):

        str_query='DELETE FROM Review ' \
                  'WHERE assignment_id= ' + assignment_id + ' AND criterion_id= ' + criterion_id + ' AND reviewee = ' + reviewee_id
        self.cur.execute(str_query)

class ReviewSummarizer:

    LANGUAGE = "english"
    DEFAULT_ALGORITHM = "textrank"
    DEFAULT_LEN = 10

    def __init__(self):
        self.dal = ReviewDAL()

    def get_summary_by_assignment_criterion(self, aid, cid, length=DEFAULT_LEN, algorithm=DEFAULT_ALGORITHM):
        row = self.dal.get_reviews_by_assignment_criterion(aid, cid)
        if len(row) == 0 :
            return ''
        else:
            # comments = [{"reviewer_id":item[0], reviewee_id":item[1], "score":item[2], "feedback":item[3]} for item in row]
            corpus = ". ".join([item['feedback'] for item in row])
            return self.summarize(corpus, length, algorithm)

    def get_summary_by_assignment_criterion_reviewee(self, aid, cid, sid, length=DEFAULT_LEN, algorithm=DEFAULT_ALGORITHM):
        row = self.dal.get_reviews_by_assignment_criterion_reviewee(aid, cid, sid)
        if len(row) == 0 :
            return ''
        else:
            # comments = [{"reviewer_id":item[0], "score":item[1], "feedback":item[2]} for item in row]
            corpus = ". ".join([item['feedback'] for item in row])
            return self.summarize(corpus, length, algorithm)


    def get_summary_by_assignment_reviewee(self, aid, sid, length=DEFAULT_LEN, algorithm=DEFAULT_ALGORITHM):
        row = self.dal.get_reviews_by_assignment_reviewee(aid, sid)
        if len(row) == 0 :
            return ''
        else:
            # comments = [{"reviewer_id":item[0], criterion_id":item[1], "score":item[2], "feedback":item[3]} for item in row]
            corpus = ". ".join([item['feedback'] for item in row])
            return self.summarize(corpus, length, algorithm)

    def summarize(self, corpus, length, algorithm):
        parser = PlaintextParser.from_string(corpus,Tokenizer(self.LANGUAGE))

        if algorithm == "textrank":
            summarizer = TextRankSummarizer(Stemmer(self.LANGUAGE))
        elif algorithm == "lexrank":
            summarizer = LexRankSummarizer(Stemmer(self.LANGUAGE))
        elif algorithm == "luhn":
            summarizer = LuhnSummarizer(Stemmer(self.LANGUAGE))
        elif algorithm == "edmundson":
            summarizer = EdmundsonSummarizer(Stemmer(self.LANGUAGE))
        elif algorithm == "kl":
            summarizer = KLSummarizer(Stemmer(self.LANGUAGE))
        elif algorithm == "lsa":
            summarizer = LsaSummarizer(Stemmer(self.LANGUAGE))
        elif algorithm == "sumbasic":
            summarizer = SumBasicSummarizer(Stemmer(self.LANGUAGE))
        elif algorithm == "random":
            summarizer = RandomSummarizer(Stemmer(self.LANGUAGE))
        else:
            raise NotImplemented("Summary algorithm is not available")

        summarizer.stop_words = get_stop_words(self.LANGUAGE)
        summary = " ".join([obj._text for obj in summarizer(parser.document, length)])

        return summary


app = Flask(__name__)
api = Api(app, version='1.0', title='Summary API',
    description='A simple summarization API with sumy library',
)

ns = api.namespace('v1.0', 'Text Summary v 1.0 ')

parser = api.parser()
parser.add_argument('reviews', required=True, location='json', help='Input Format -> {"reviews":[ {"reviewer_id":"string","reviewee_id":"string","score":"string","feedback":"string"}]}')

parser_sum = api.parser()
parser_sum.add_argument('sentences', required=True, location='json', help='Input Format -> {"sentences":[ "sentence1" ]')


###### Definition of data model for documentation
summary_marshaller = api.model('summary_marshaller',{
    'summary': fields.String(description='Summary of the review')
})

message_marshaller = api.model('message_marshaller',{
    'message': fields.String(description='Api call status', required=True)
})

review_marshaller = api.model('review_marshaller',{
    'reviewer_id': fields.String(description='reviewer ID', required=True),
    'reviewee_id': fields.String(description='reviewee ID', required=True),
    'score': fields.String(description='score', required=True),
    'feedback': fields.String(description='textual feedback', required=True)
})

review_list_marshaller = api.model('review_list_marshaller',{
    'reviews': fields.List(fields.Nested(review_marshaller, description='a list of feedbacks on an assignment')),
})
###### Definition of data model for documentation

MESSAGE_DOESNT_EXIST = "cannot find record with those ids"
MESSAGE_ADDED = 'reviews added'
MESSAGE_DELETED = 'reviews deleted'
SUPPORTED_ALGORITHMS = ['textrank', 'lexrank', 'luhn', 'edmonson', 'kl', 'lsa', 'sumbasic', 'random']
MESSAGE_ALGORITHM_NOT_SUPPORTED = 'the algorithm you chosed is not supported , please use: textrank, lexrank, luhn, edmonson, kl, lsa, sumbasic, random'

########ByAssignmentCriteria
@ns.route('/assignment/<string:aid>/criterion/<string:cid>/reviews')
@api.doc(params={'aid': 'The assignment ID', 'cid': 'The criteria ID'})
class ReviewByAssignmentCriteria(Resource):

    dal = ReviewDAL()

    '''Show a list of reviews on an assignment based on a criteria'''
    @api.marshal_list_with(review_list_marshaller, code=200)
    def get(self, aid, cid):
        '''Fetch list of reviews on an assignment based on a criteria'''
        results = self.dal.get_reviews_by_assignment_criterion(aid,cid)
        try:
            return marshal({'reviews':results}, review_list_marshaller), 200
        except Exception as e:
            abort(500, message=str(e))

    '''Delete a list of reviews on an assignment based on a criteria'''
    @api.marshal_with(message_marshaller)
    def delete(self, aid, cid):
        '''Delete reviews given assignment id and criterion id'''
        if not self.dal.is_record_exist(aid, criterion_id=cid):
            abort(404, message=MESSAGE_DOESNT_EXIST)
        else:
            self.dal.del_reviews_by_assignment_criterion(aid, cid)
            return marshal({'message':MESSAGE_DELETED}, message_marshaller), 200

    '''Add a list of reviews on an assignment based on a criteria'''
    @api.doc(parser=parser)
    @api.marshal_with(message_marshaller)
    def post(self, aid, cid):
        '''Update all reviews given assignment id and criterion id'''
        try:
            js = request.get_json()
            tuples = [(aid, cid, row["reviewer_id"],row["reviewee_id"], row["score"], row["feedback"]) for row in js["reviews"]]
            self.dal.insert_tuples(tuples)
        except Exception as e:
            abort(500, message=str(e))
        return marshal({'message':MESSAGE_ADDED}, message_marshaller), 200

@ns.route('/assignment/<string:aid>/criterion/<string:cid>/reviews/summary')
@api.doc(params={'aid': 'The assignment ID', 'cid': 'The criteria ID'})
class SummaryByAssignmentCriteria(Resource):

    sum = ReviewSummarizer()


    @api.doc(description='aid and cid should be unique')
    @api.marshal_with(summary_marshaller)
    def get(self, aid, cid):
        '''Summarize reviews given assignment id and criterion id'''
        results = self.sum.get_summary_by_assignment_criterion(aid, cid)
        try:
            return marshal({'summary':results}, summary_marshaller), 200
        except Exception as e:
             abort(500, message=str(e))

@ns.route('/assignment/<string:aid>/criterion/<string:cid>/reviews/summary/<int:length>')
@api.doc(params={'aid': 'The assignment ID', 'cid': 'The criteria ID', 'length': 'Length of the summary'})
class SummaryLengthByAssignmentCriteria(Resource):

    sum = ReviewSummarizer()

    @api.doc(description='aid and cid should be unique')
    @api.marshal_with(summary_marshaller)
    def get(self, aid, cid, length):
        '''Summarize reviews given assignment id, criterion id, and length of the summary'''
        results = self.sum.get_summary_by_assignment_criterion(aid, cid, length=length)
        try:
            return marshal({'summary':results}, summary_marshaller), 200
        except Exception as e:
             abort(500, message=str(e))

@ns.route('/assignment/<string:aid>/criterion/<string:cid>/reviews/summary/<int:length>/<string:algorithm>')
@api.doc(params={'aid': 'The assignment ID', 'cid': 'The criteria ID', 'length': 'Length of the summary', 'algorithm': 'summarization algorithm, please choose on of these: textrank, lexrank, luhn, edmonson, kl, lsa, sumbasic, random'})
class SummaryLengthAlgorithmByAssignmentCriteria(Resource):

    sum = ReviewSummarizer()

    @api.doc(description='aid and cid should be unique')
    @api.marshal_with(summary_marshaller)
    def get(self, aid, cid, length, algorithm):
        '''Summarize reviews given assignment id, criterion id, length of the summary, and algorithm to use'''
        alg = str(algorithm).lower()
        if not alg in SUPPORTED_ALGORITHMS:
            abort(404, message=MESSAGE_ALGORITHM_NOT_SUPPORTED)

        results = self.sum.get_summary_by_assignment_criterion(aid, cid, length=length, algorithm=alg)
        try:
            return marshal({'summary':results}, summary_marshaller), 200
        except Exception as e:
            abort(500, message=str(e))       


#########ByAssignmentReviewee

@ns.route('/assignment/<string:aid>/reviewee/<string:sid>/reviews')
@api.doc(params={'aid': 'The assignment ID', 'sid': 'The reviewee ID'})
class ReviewByAssignmentReviewee(Resource):
    dal = ReviewDAL()

    '''Show a list of reviews on an assignment based on a reviewee'''
    @api.marshal_with(review_list_marshaller, code=200)
    def get(self, aid, sid):
        '''Fetch reviews given assignment id and reviewee id'''
        results = self.dal.get_reviews_by_assignment_reviewee(aid,sid)
        try:
            return marshal({'summary':results}, summary_marshaller), 200
        except Exception as e:
            abort(500, message=str(e))

    '''Delete a list of reviews on an assignment based on a reviewee'''
    @api.marshal_with(message_marshaller)
    def delete(self, aid, sid):
        '''Delete reviews given assignment id and reviewee id'''
        if not self.dal.is_record_exist(aid, reviewee_id=sid):
            abort(404, message=MESSAGE_DOESNT_EXIST)
        else:
            self.dal.del_reviews_by_assignment_criterion(aid, sid)
            return marshal({'message':MESSAGE_DELETED}, message_marshaller), 200

    '''Add a list of reviews on an assignment based on a reviewee'''
    @api.doc(parser=parser)
    @api.marshal_with(message_marshaller)
    def post(self, aid, sid):
        '''Add all reviews given assignment id and reviewee id'''
        try:
            js = request.get_json()
            tuples = [(aid, sid, row["reviewer_id"],row["criterion_id"], row["score"], row["feedback"]) for row in js["reviews"]]
            self.dal.insert_tuples(tuples)
        except Exception as e:
            abort(500, message=str(e))
        return marshal({'message':MESSAGE_ADDED}, message_marshaller), 200

@ns.route('/assignment/<string:aid>/reviewee/<string:sid>/reviews/summary')
@api.doc(params={'aid': 'The assignment ID', 'sid': 'The reviewee ID'})
class SummaryByAssignmentReviewee(Resource):

    sum = ReviewSummarizer()

    @api.marshal_with(summary_marshaller)
    @api.doc(description='aid and cid should be unique')
    def get(self, aid, sid):
        '''Summarize reviews given assignment id and reviewee id'''
        results = self.sum.get_summary_by_assignment_reviewee(aid, sid)
        try:
            return marshal({'summary':results}, summary_marshaller), 200
        except Exception as e:
            abort(500, message=str(e)) 

@ns.route('/assignment/<string:aid>/reviewee/<string:sid>/reviews/summary/<int:length>')
@api.doc(params={'aid': 'The assignment ID', 'sid': 'The reviewee ID', 'length': 'Length of the summary'})
class SummaryLengthByAssignmentReviewee(Resource):

    sum = ReviewSummarizer()

    @api.doc(description='aid and sid should be unique')
    @api.marshal_with(summary_marshaller)
    def get(self, aid, sid, len):
        '''Summarize reviews given assignment id, reviewee id and length of the summary'''
        results = self.sum.get_summary_by_assignment_reviewee(aid, sid, length=len)
        try:
            return marshal({'summary':results}, summary_marshaller), 200
        except Exception as e:
            abort(500, message=str(e))

@ns.route('/assignment/<string:aid>/reviewee/<string:sid>/reviews/summary/<int:length>/<string:algorithm>')
@api.response(404, 'Algorithm not found')
@api.response(200, 'Succeed executing the command')
@api.doc(params={'aid': 'The assignment ID', 'sid': 'The reviewee ID', 'length': 'Length of the summary', 'algorithm': 'summarization algorithm, please choose on of these: textrank, lexrank, luhn, edmonson, kl, lsa, sumbasic, random'})
class SummaryLengthAlgorithmByAssignmentReviewee(Resource):

    sum = ReviewSummarizer()

    @api.doc(description='aid and cid should be unique')
    @api.marshal_with(summary_marshaller)
    def get(self, aid, cid, len, alg):
        '''Summarize reviews given assignment id, reviewee id, and length of the summary'''
        alg = str(alg).lower()
        if not alg in SUPPORTED_ALGORITHMS:
            return marshal({'message':MESSAGE_ALGORITHM_NOT_SUPPORTED}, message_marshaller), 404

        results = self.sum.get_summary_by_assignment_criterion(aid, cid, length=len, algorithm=alg)
        try:
            return marshal({'summary':results}, summary_marshaller), 200
        except Exception as e:
            abort(500, message=str(e))

##########ByAssignmentRevieweeCriteria
@ns.route('/assignment/<string:aid>/reviewee/<string:sid>/criterion/<string:cid>/reviews')
@api.response(404, 'reviews not found')
@api.doc(params={'aid': 'The assignment ID', 'sid': 'The reviewee ID', 'cid': 'The criterion ID'})
class ReviewByAssignmentRevieweeCriteria(Resource):
    dal = ReviewDAL()

    '''Show a list of reviews on an assignment based on a reviewee'''
    @api.marshal_with(review_list_marshaller, code=200)
    def get(self, aid, sid, cid):
        '''Fetch reviews given assignment id, reviewee id, and criterion id'''
        results = self.dal.get_reviews_by_assignment_criterion_reviewee(aid, sid, cid)
        try:
            return marshal({'reviews':results}, review_list_marshaller), 200
        except Exception as e:
            abort(500, message=str(e))

    '''Delete a list of reviews on an assignment based on a reviewee'''
    @api.marshal_with(message_marshaller)
    def delete(self, aid, sid, cid):
        '''Delete reviews given assignment id, reviewee id, and criterion id'''
        if not self.dal.is_record_exist(aid, reviewee_id=sid, criterion_id=cid):
            abort(404, message=MESSAGE_DOESNT_EXIST)
        else:
            self.dal.del_reviews_by_assignment_criterion_reviewee(aid, sid, cid)
            return marshal({'message':MESSAGE_DELETED}, message_marshaller), 200

    '''Add a list of reviews on an assignment based on a reviewee'''
    @api.doc(parser=parser)
    @api.marshal_with(message_marshaller)
    def post(self, aid, sid, cid):
        '''Add all reviews given assignment id, reviewee id, and criterion id'''
        try:
            js = request.get_json()
            tuples = [(aid, sid, cid, row["reviewer_id"], row["score"], row["feedback"]) for row in js["reviews"]]
            self.dal.insert_tuples(tuples)
        except Exception as e:
            return abort(500, message=str(e))
        return marshal({'message':MESSAGE_ADDED}, message_marshaller), 200

@ns.route('/assignment/<string:aid>/reviewee/<string:sid>/criterion/<string:cid>/reviews/summary')
@api.doc(params={'aid': 'The assignment ID', 'sid': 'reviewee_id', 'cid': 'The criteria ID'})
class SummaryByAssignmentRevieweeCriteria(Resource):

    sum = ReviewSummarizer()
    @api.marshal_with(summary_marshaller)
    @api.doc(description='aid, sid, cid should be unique')
    def get(self, aid, sid, cid):
        '''Summarize reviews given assignment id, reviewee id and criterion id'''
        results = self.sum.get_summary_by_assignment_criterion_reviewee(aid, cid, sid)
        try:
            return marshal({'summary':results}, summary_marshaller), 200
        except Exception as e:
            abort(500, message=str(e))

@ns.route('/assignment/<string:aid>/reviewee/<string:sid>/criterion/<string:cid>/reviews/summary/<int:length>')
@api.doc(params={'aid': 'The assignment ID', 'cid': 'The criteria ID', 'length': 'Length of the summary'})
class SummaryLengthByAssignmentCriteria(Resource):

    sum = ReviewSummarizer()

    @api.doc(description='aid and cid should be unique')
    @api.marshal_with(summary_marshaller)
    def get(self, aid, sid, cid, length):
        '''Summarize reviews given assignment id, reviewee id, criterion id, and length of the summary'''
        results = self.sum.get_summary_by_assignment_criterion_reviewee(aid,cid,sid, length=length)
        try:
            return marshal({'summary':results}, summary_marshaller), 200
        except Exception as e:
            abort(500, message=str(e))

@ns.route('/assignment/<string:aid>/reviewee/<string:sid>/criterion/<string:cid>/reviews/summary/<length>/<algorithm>')
@api.response(404, 'Assignment not found')
@api.doc(params={'aid': 'The assignment ID', 'cid': 'The criteria ID', 'length': 'Length of the summary'})
class SummaryLengthAlgorithmByAssignmentCriteria(Resource):

    sum = ReviewSummarizer()

    @api.doc(description='aid and cid should be unique')
    @api.marshal_with(summary_marshaller)
    def get(self, aid, sid, cid, length, algorithm):
        '''Summarize reviews given assignment id, reviewee id, criterion id, and length of the summary'''
        alg = str(algorithm).lower()
        if not alg in SUPPORTED_ALGORITHMS:
            return marshal({'message':MESSAGE_ALGORITHM_NOT_SUPPORTED}, message_marshaller), 404

        results = self.sum.get_summary_by_assignment_criterion_reviewee(aid,cid,sid, length=length, algorithm=alg)
        try:
            return marshal({'summary':results}, summary_marshaller), 200
        except Exception as e:
            abort(500, message=str(e))

@ns.route('/summary')
class GenericSummary(Resource):

    sum = ReviewSummarizer()

    @api.doc(parser=parser)
    @api.marshal_with(summary_marshaller)
    def post(self):
        '''Summarize a given set of sentences'''
        try:
            js = request.get_json()
            results = self.sum.get_summary_generic(js)
            return marshal({'summary':results}, summary_marshaller), 200
        except Exception as e:
            abort(500, message=str(e))

@ns.route('/summary/<length>')
class SummaryLen(Resource):

    sum = ReviewSummarizer()

    @api.doc(parser=parser)
    @api.marshal_with(summary_marshaller)
    def post(self, length):
        '''Summarize a given set of sentences and length of the summary'''
        try:
            js = request.get_json()
            results = self.sum.get_summary_generic(js, length=length)
            return marshal({'summary':results}, summary_marshaller), 200
        except Exception as e:
            abort(500, message=str(e))

@ns.route('/summary/<length>/<algorithm>')
class SummaryLen(Resource):

    sum = ReviewSummarizer()

    @api.doc(parser=parser)
    @api.marshal_with(summary_marshaller)
    def post(self, length, algorithm):
        '''Summarize a given set of sentences, length of the summar, and type of algorithm'''
        try:
            js = request.get_json()
            results=self.sum.get_summary_generic(js, length, algorithm)
            return marshal({'summary':results}, summary_marshaller), 200
        except Exception as e:
            abort(500, message=str(e))





if __name__ == '__main__':
    app.run()



