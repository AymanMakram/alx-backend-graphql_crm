import graphene
from crm.schema import CRMQuery, Mutation as CRMMutation

class CRMQuery(graphene.ObjectType):
    hello = graphene.String()

    def resolve_hello(self, info):
        return "Hello, GraphQL!"


class Query(CRMQuery, graphene.ObjectType):
    pass


class Mutation(CRMMutation, graphene.ObjectType):
    pass


schema = graphene.Schema(query=Query, mutation=Mutation)