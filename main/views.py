from SPARQLWrapper import JSON, SPARQLWrapper
from django.shortcuts import render
from django.http import JsonResponse

sparql = SPARQLWrapper(
    "http://localhost:7200/repositories/tk-final"
)

sparql.setReturnFormat(JSON)


def show_main(request):
    sparql.setQuery("""
        select * where {
            ?s ?p ?o .
        } limit 100
    """)

    results = sparql.queryAndConvert()['results']['bindings']

    return JsonResponse(results, safe=False)
    # return render(request, 'main.html', {"results": results})
