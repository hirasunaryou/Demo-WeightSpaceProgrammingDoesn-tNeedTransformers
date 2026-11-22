import torch


def bags(w, q, o):
    """Question and option bags over concepts, idf-weighted: (n, C) and (n, 4, C). A word's concept is
    w["concept"][word id] (concept 0: none); an option keeps only the concepts the question does not have."""
    n, C = q.shape[0], w["idf"].shape[0]
    real = (torch.arange(C) > 0).float()
    qb = torch.zeros(n, C).scatter_(1, w["concept"][q], 1.0) * real
    ob = torch.zeros(n * 4, C).scatter_(1, w["concept"][o].reshape(n * 4, -1), 1.0).reshape(n, 4, C) * real
    return qb * w["idf"], ob * (1.0 - qb)[:, None, :] * w["idf"]


J, PRIME = 16, 1000003


def forward(w, q, o):
    """Second-order association memory: what two question concepts together recall. The question's J strongest
    concepts form J (J - 1) / 2 pairs; the pair of concepts a < b is row (a * PRIME + b) % H of a table whose row
    lists the concepts that pair recalls, with weights (w["row_ids"], w["row_w"]: (H, R)). The rows of all the
    question's pairs, each weighted by its two concepts' idf, are added into a bag, plus `mix` times the
    first-order read q A (w["A"]: (C, C), as in a first-order association memory). Every fact is folded into the
    tables when the model is built, so the work per question does not depend on how many facts were written. An
    option's score is how much of it the bag covers."""
    n, C = q.shape[0], w["idf"].shape[0]
    qb, ob = bags(w, q, o)
    top = qb.topk(J, dim=1)
    a, b = torch.triu_indices(J, J, 1)
    lo = torch.minimum(top.indices[:, a], top.indices[:, b])
    hi = torch.maximum(top.indices[:, a], top.indices[:, b])
    rows = (lo * PRIME + hi) % w["row_ids"].shape[0]                                  # (n, pairs)
    strength = top.values[:, a] * top.values[:, b]                                    # 0 for a missing concept
    read = torch.zeros(n, C).scatter_add_(1, w["row_ids"][rows].reshape(n, -1),
                                          (strength[:, :, None] * w["row_w"][rows]).reshape(n, -1))
    read = (read + w["mix"] * (qb @ w["A"])) * (qb == 0).float()
    return torch.einsum("nc,nkc->nk", read, ob)
