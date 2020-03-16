from flask import jsonify, request, g
from flask_cors import cross_origin
from sqlalchemy import desc

from app.api.base import api_bp, verify_api_key
from app.config import ALIAS_DOMAINS, DISABLE_ALIAS_SUFFIX
from app.extensions import db
from app.log import LOG
from app.models import AliasUsedOn, GenEmail, User
from app.utils import convert_to_id, random_word


@api_bp.route("/alias/options")
@cross_origin()
@verify_api_key
def options():
    """
    Return what options user has when creating new alias.
    Input:
        a valid api-key in "Authentication" header and
        optional "hostname" in args
    Output: cf README
        optional recommendation:
        optional custom
        can_create_custom: boolean
        existing: array of existing aliases

    """
    LOG.warning("/v2/alias/options should be used instead")
    user = g.user
    hostname = request.args.get("hostname")

    ret = {
        "existing": [ge.email for ge in GenEmail.query.filter_by(user_id=user.id)],
        "can_create_custom": user.can_create_new_alias(),
    }

    # recommendation alias if exist
    if hostname:
        # put the latest used alias first
        q = (
            db.session.query(AliasUsedOn, GenEmail, User)
            .filter(
                AliasUsedOn.gen_email_id == GenEmail.id,
                GenEmail.user_id == user.id,
                AliasUsedOn.hostname == hostname,
            )
            .order_by(desc(AliasUsedOn.created_at))
        )

        r = q.first()
        if r:
            _, alias, _ = r
            LOG.d("found alias %s %s %s", alias, hostname, user)
            ret["recommendation"] = {"alias": alias.email, "hostname": hostname}

    # custom alias suggestion and suffix
    ret["custom"] = {}
    if hostname:
        # keep only the domain name of hostname, ignore TLD and subdomain
        # for ex www.groupon.com -> groupon
        domain_name = hostname
        if "." in hostname:
            parts = hostname.split(".")
            domain_name = parts[-2]
            domain_name = convert_to_id(domain_name)
        ret["custom"]["suggestion"] = domain_name
    else:
        ret["custom"]["suggestion"] = ""

    ret["custom"]["suffixes"] = []
    # maybe better to make sure the suffix is never used before
    # but this is ok as there's a check when creating a new custom alias
    for domain in ALIAS_DOMAINS:
        if DISABLE_ALIAS_SUFFIX:
            ret["custom"]["suffixes"].append(f"@{domain}")
        else:
            ret["custom"]["suffixes"].append(f".{random_word()}@{domain}")

    for custom_domain in user.verified_custom_domains():
        ret["custom"]["suffixes"].append("@" + custom_domain.domain)

    # custom domain should be put first
    ret["custom"]["suffixes"] = list(reversed(ret["custom"]["suffixes"]))

    return jsonify(ret)


@api_bp.route("/v2/alias/options")
@cross_origin()
@verify_api_key
def options_v2():
    """
    Return what options user has when creating new alias.
    Input:
        a valid api-key in "Authentication" header and
        optional "hostname" in args
    Output: cf README
        can_create: bool
        suffixes: [str]
        prefix_suggestion: str
        existing: [str]
        recommendation: Optional dict
            alias: str
            hostname: str


    """
    user = g.user
    hostname = request.args.get("hostname")

    ret = {
        "existing": [
            ge.email for ge in GenEmail.query.filter_by(user_id=user.id, enabled=True)
        ],
        "can_create": user.can_create_new_alias(),
        "suffixes": [],
        "prefix_suggestion": "",
    }

    # recommendation alias if exist
    if hostname:
        # put the latest used alias first
        q = (
            db.session.query(AliasUsedOn, GenEmail, User)
            .filter(
                AliasUsedOn.gen_email_id == GenEmail.id,
                GenEmail.user_id == user.id,
                AliasUsedOn.hostname == hostname,
            )
            .order_by(desc(AliasUsedOn.created_at))
        )

        r = q.first()
        if r:
            _, alias, _ = r
            LOG.d("found alias %s %s %s", alias, hostname, user)
            ret["recommendation"] = {"alias": alias.email, "hostname": hostname}

    # custom alias suggestion and suffix
    if hostname:
        # keep only the domain name of hostname, ignore TLD and subdomain
        # for ex www.groupon.com -> groupon
        domain_name = hostname
        if "." in hostname:
            parts = hostname.split(".")
            domain_name = parts[-2]
            domain_name = convert_to_id(domain_name)
        ret["prefix_suggestion"] = domain_name

    # maybe better to make sure the suffix is never used before
    # but this is ok as there's a check when creating a new custom alias
    for domain in ALIAS_DOMAINS:
        if DISABLE_ALIAS_SUFFIX:
            ret["suffixes"].append(f"@{domain}")
        else:
            ret["suffixes"].append(f".{random_word()}@{domain}")

    for custom_domain in user.verified_custom_domains():
        ret["suffixes"].append("@" + custom_domain.domain)

    # custom domain should be put first
    ret["suffixes"] = list(reversed(ret["suffixes"]))

    return jsonify(ret)
