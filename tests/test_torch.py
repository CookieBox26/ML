import torch
import torch.nn as nn
from math import sqrt


class TestTorch:

    def test_einsum(self):
        """ torch.einsum の結果を確認する．
        """
        # 簡単な例．ただの行列積．
        a = torch.tensor([[1., 2., 3.], [4., 5., 6.]])
        b = torch.tensor([[1., 2.], [3., 4.], [5., 6,]])
        c = torch.einsum('ij,jk->ik', a, b)
        # ただの行列積に一致することを確認．
        assert torch.all(torch.eq(c, torch.matmul(a, b)))
        # 手で検算．
        c_ = torch.zeros(a.shape[0], b.shape[1])
        for i in range(a.shape[0]):
            for j in range(a.shape[1]):
                for k in range(b.shape[1]):
                    c_[i][k] += a[i][j] * b[j][k]
        assert torch.all(torch.eq(c, c_))

        # バッチサイズ1, 系列長3, ヘッド数2, 特徴次元数4 のセルフアテンションの例．
        # 'blhe,bshe->bhls' でサイズ [1, 2, 3, 3] のテンソルになる．
        # [b, h, l, s] 成分の意味は，「バッチ内 b 番目のデータの h ヘッド目の
        # l 単語目から s 単語目へのセルフアテンション（次元のルートで割ってソフトマックスする前）．
        q = torch.tensor([
            [
                [
                    [1., 2., 3., 4.],  # 1単語目の1ヘッド目のクエリ特徴
                    [5., 6., 7., 8.],  # 1単語目の2ヘッド目のクエリ特徴
                ],
                [
                    [10., 20., 30., 40.],  # 2単語目の1ヘッド目のクエリ特徴
                    [50., 60., 70., 80.],  # 2単語目の2ヘッド目のクエリ特徴
                ],
                [
                    [100., 200., 300., 400.],  # 3単語目の1ヘッド目のクエリ特徴
                    [500., 600., 700., 800.],  # 3単語目の2ヘッド目のクエリ特徴
                ],
            ],
        ])
        k = torch.tensor([
            [
                [
                    [0.1, 0.2, 0.3, 0.4],  # 1単語目の1ヘッド目のキー特徴
                    [0.1, 0.2, 0.3, 0.4],  # 1単語目の2ヘッド目のキー特徴
                ],
                [
                    [0.1, 0.0, 0.0, 0.0],  # 2単語目の1ヘッド目のキー特徴
                    [0.0, 0.1, 0.0, 0.0],  # 2単語目の2ヘッド目のキー特徴
                ],
                [
                    [0.0, 0.0, 0.1, 0.0],  # 3単語目の1ヘッド目のキー特徴
                    [0.0, 0.0, 0.0, 0.1],  # 3単語目の2ヘッド目のキー特徴
                ],
            ],
        ])
        scores = torch.einsum('blhe,bshe->bhls', q, k)
        # バッチ内 0 番目のデータの 0 ヘッド目のセルフアテンションを転置で計算するならこう．
        assert torch.all(
            torch.eq(
                scores[0][0],
                torch.matmul(torch.transpose(q[0], 0, 1)[0], torch.transpose(torch.transpose(k[0], 0, 1)[0], 0, 1))
            )
        )
        # 手で検算．
        scores_ = torch.zeros(q.shape[0], q.shape[2], q.shape[1], k.shape[1])
        for b in range(q.shape[0]):
            for l in range(q.shape[1]):
                for h in range(q.shape[2]):
                    for e in range(q.shape[3]):
                        for s in range(k.shape[1]):
                            scores_[b][h][l][s] += q[b][l][h][e] * k[b][s][h][e]
        assert torch.all(torch.eq(scores, scores_))

    def test_masked_fill_(self):
        # 以下のセルフアテンションをマスクする．
        scores = torch.tensor([[
            [
                [1., 2., 3.],
                [4., 5., 6.],
                [7., 8., 9.],
            ]
        ]])

        # まず未来へのアテンションが True になる行列を用意する．
        mask = torch.triu(torch.ones([1, 1, 3, 3], dtype=torch.bool), diagonal=1)
        assert torch.all(torch.eq(
            mask,
            torch.tensor([[
                [False, True, True],
                [False, False, True],
                [False, False, False],
            ]])
        ))

        # 以下のようにすると未来へのアテンションを -inf にできる．
        scores.masked_fill_(mask, float('-inf'))
        assert torch.all(torch.eq(
            scores,
            torch.tensor([[
                [1., float('-inf'), float('-inf')],
                [4., 5., float('-inf')],
                [7., 8., 9.],
            ]])
        ))

        # ついでに正規化とドロップアウトまでするとこう．
        attn = torch.softmax((1./sqrt(3)) * scores, dim=-1)
        # print(attn)  # マスク箇所が 0.0 になる．
        dropout = nn.Dropout(0.5)
        attn = dropout(attn)
        # print(attn)  # 50% の成分が 0.0 になり生き残った成分が 2 倍になる．

        # ついでにセルフアテンションの適用までするとこう．
        v = torch.tensor([[
            [[0.1, 0.2, 0.3, 0.4]],
            [[0.5, 0.6, 0.7, 0.8]],
            [[0.1, 0.1, 0.1, 0.1]],
        ]])
        v = torch.einsum('bhls,bshd->blhd', attn, v)


    def test_unsqueeze(self):
        """ torch.unsqueeze の使い方を確認する．
        参考文献. https://github.com/zhouhaoyi/Informer2020/blob/main/models/attn.py
        """
        # バッチサイズ1, 系列長5, ヘッド数1, 特徴次元数4
        q = torch.tensor([[
            [[1., 2., 3., 4.]],
            [[5., 6., 7., 8.]],
            [[1., 2., 1., 2.]],
            [[3., 4., 3., 4.]],
            [[5., 6., 5., 6.]],
        ]])
        k = torch.tensor([[
            [[0.1, 0.2, 0.3, 0.4]],
            [[0.1, 0.0, 0.0, 0.0]],
            [[0.0, 0.1, 0.0, 0.0]],
            [[0.0, 0.0, 0.1, 0.0]],
            [[0.0, 0.0, 0.0, 0.1]],
        ]])
        assert k.shape == torch.Size([1, 5, 1, 4])

        # 系列長とヘッド数を転置
        # --> バッチ, ヘッド, 系列長, 特徴次元
        q = q.transpose(2, 1)
        k = k.transpose(2, 1)
        assert k.shape == torch.Size([1, 1, 5, 4])

        B, H, L_K, E = k.shape
        _, _, L_Q, _ = q.shape
        assert k.unsqueeze(-1).shape == torch.Size([1, 1, 5, 4, 1])
        assert k.unsqueeze(-2).shape == torch.Size([1, 1, 5, 1, 4])
        assert k.unsqueeze(-3).shape == torch.Size([1, 1, 1, 5, 4])

        # バッチ, ヘッド, 系列長*, 系列長, 特徴次元
        # になるように軸を割り込ませてコピー
        k_expand = k.unsqueeze(-3).expand(B, H, L_Q, L_K, E)
        assert k_expand.shape == torch.Size([1, 1, 5, 5, 4])
        assert torch.all(torch.eq(k[0][0], k_expand[0][0][0]))
        assert torch.all(torch.eq(k[0][0], k_expand[0][0][1]))
        assert torch.all(torch.eq(k[0][0], k_expand[0][0][2]))
        assert torch.all(torch.eq(k[0][0], k_expand[0][0][3]))
        assert torch.all(torch.eq(k[0][0], k_expand[0][0][4]))

        # 通常のセルフアテンションであれば 5×5 個の成分を計算しなければならない．
        # 計算量を節約するために k 側を 3 本に間引く．
        # q の各行によって間引き方を変えるので 3 本の選び方を 5 セット用意する．
        sample_k = 3
        torch.manual_seed(0)
        index_sample = torch.randint(L_K, (L_Q, sample_k))
        assert index_sample.shape == torch.Size([5, 3])  # 3 本の選び方が 5 セット
        k_sample = k_expand[:, :, torch.arange(L_Q).unsqueeze(1), index_sample, :]
        assert k_sample.shape == torch.Size([1, 1, 5, 3, 4])

        assert q.unsqueeze(-2).shape == torch.Size([1, 1, 5, 1, 4])  # q を行ごとにほぐす．
        assert k_sample.transpose(-2, -1).shape == torch.Size([1, 1, 5, 4, 3])  # 行ごとに異なる 4×3 にあてる．
        assert torch.matmul(q.unsqueeze(-2), k_sample.transpose(-2, -1)).shape == torch.Size([1, 1, 5, 1, 3])
        q_k_sample = torch.matmul(q.unsqueeze(-2), k_sample.transpose(-2, -1)).squeeze()
        assert q_k_sample.shape == torch.Size([5, 3])

        # 一様分布との交差エントロピーの見積もり値が大きい3行を残す．
        n_top = 3
        M = q_k_sample.max(-1)[0] - torch.div(q_k_sample.sum(-1), L_K)
        assert M.shape == torch.Size([5])
        M_top = M.topk(n_top, sorted=False)[1]  # 値とインデックスのタプルなので [1] でインデックスをとる．
        assert M_top.shape == torch.Size([3])
        assert torch.all(torch.eq(M_top, torch.tensor([4, 1, 0])))

        q_reduce = q[torch.arange(B)[:, None, None], torch.arange(H)[None, :, None], M_top, :]
        assert q_reduce.shape == torch.Size([1, 1, 3, 4])
        q_k = torch.matmul(q_reduce, k.transpose(-2, -1))
        assert q_k.shape == torch.Size([1, 1, 3, 5])

        # 未来へのセルフアテンションをマスクする．
        v = torch.ones([1, 5, 1, 4])
        v = v.transpose(2, 1)
        B, H, L_V, D = v.shape
        _mask = torch.ones(L_Q, q_k.shape[-1], dtype=torch.bool).triu(1)  # 対角成分より上が True の行列
        _mask_ex = _mask[None, None, :].expand(B, H, L_Q, q_k.shape[-1])
        assert torch.all(torch.eq(
            _mask_ex,
            torch.tensor([[
                [False, True, True, True, True],
                [False, False, True, True, True],
                [False, False, False, True, True],
                [False, False, False, False, True],
                [False, False, False, False, False],
            ]])
        ))
        indicator = _mask_ex[torch.arange(B)[:, None, None], torch.arange(H)[None, :, None], M_top, :]
        mask = indicator.view(q_k.shape)
        assert torch.all(torch.eq(
            mask,
            torch.tensor([[
                [False, False, False, False, False],
                [False, False, True, True, True],
                [False, True, True, True, True],
            ]])
        ))
        q_k.masked_fill_(mask, float('-inf'))
        attn = torch.softmax(q_k, dim=-1)

        # v にセルフアテンションを適用する．
        # 間引かれた行の v は単にその行までの cumsum になる．
        # セルフアテンションの間引かれた行には行にわたる一様分布がはめられるがこれを適用したわけではない．
        context = v.cumsum(dim=-2)
        context[torch.arange(B)[:, None, None], torch.arange(H)[None, :, None], M_top, :] \
            = torch.matmul(attn, v).type_as(context)
        attns = (torch.ones([B, H, L_V, L_V]) / L_V).type_as(attn)
        attns[torch.arange(B)[:, None, None], torch.arange(H)[None, :, None], M_top, :] = attn
