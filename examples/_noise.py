"""Qubit.measure의 decoherence_rate 키워드를 내장 잡음 함수의 p로 연결함."""

from qns.models.qubit.decoherence import BitFlipError


def bit_flip_measure_error(qubit, decoherence_rate=0, **kwargs):
    BitFlipError(qubit, p=decoherence_rate)
