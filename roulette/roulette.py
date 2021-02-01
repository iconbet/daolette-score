from iconservice import *

TAG = 'ROUL'

# Treasury minimum 2.5E+23, or 250,000 ICX.
TREASURY_MINIMUM = 250000000000000000000000

BET_LIMIT_RATIOS = [147, 2675, 4315, 2725, 1930, 1454, 1136, 908, 738, 606,
                    500, 413, 341, 280, 227, 182, 142, 107, 76, 48, 23]
BET_MIN = 100000000000000000  # 1.0E+17, .1 ICX
U_SECONDS_DAY = 86400000000 # Microseconds in a day.

TX_MIN_BATCH_SIZE = 10
TX_MAX_BATCH_SIZE = 500
DIST_DURATION_PARAM = 50  # Units of 1/Days

BET_TYPES = ["none", "bet_on_numbers", "bet_on_color", "bet_on_even_odd", "bet_on_number", "number_factor"]
WHEEL_ORDER = ["2", "20", "3", "17", "6", "16", "7", "13", "10", "12",
               "11", "9", "14", "8", "15", "5", "18", "4", "19", "1", "0"]
WHEEL_BLACK = "2,3,6,7,10,11,14,15,18,19"
SET_BLACK = {'2', '3', '6', '7', '10', '11', '14', '15', '18', '19'}
WHEEL_RED = "1,4,5,8,9,12,13,16,17,20"
SET_RED = {'1', '4', '5', '8', '9', '12', '13', '16', '17', '20'}
WHEEL_ODD = "1,3,5,7,9,11,13,15,17,19"
SET_ODD = {'1', '3', '5', '7', '9', '11', '13', '15', '17', '19'}
WHEEL_EVEN = "2,4,6,8,10,12,14,16,18,20"
SET_EVEN = {'2', '4', '6', '8', '10', '12', '14', '16', '18', '20'}
MULTIPLIERS = {"bet_on_color": 2, "bet_on_even_odd": 2, "bet_on_number": 20, "number_factor": 20.685}


# An interface of TapToken to retrieve balances
class TokenInterface(InterfaceScore):
    @interface
    def balanceOf(self, _owner: Address) -> int:
        pass

    @interface
    def totalSupply(self) -> int:
        pass


# An interface of Rewards Distribution Score to accumulate daily wagers
class RewardsInterface(InterfaceScore):
    @interface
    def accumulate_wagers(self, _player: str, _wager: int, _day_index: int) -> None:
        pass

    @interface
    def rewards_dist_complete(self) -> bool:
        pass


# An interface to the dividends score
class DividendsInterface(InterfaceScore):
    @interface
    def dividends_dist_complete(self) -> bool:
        pass

    @interface
    def get_inhouse_games(self) -> list:
        pass


# An interface of Game Authorization Score to get list of authorized game scores
class AuthInterface(InterfaceScore):
    @interface
    def get_game_status(self, _scoreAddress: Address) -> str:
        pass

    @interface
    def accumulate_daily_wagers(self, game: Address, wager: int) -> None:
        pass

    @interface
    def accumulate_daily_payouts(self, game: Address, payout: int) -> None:
        pass

    @interface
    def get_excess(self) -> int:
        pass

    @interface
    def record_excess(self) -> int:
        pass

    @interface
    def get_todays_games_excess(self) -> dict:
        pass

    @interface
    def get_yesterdays_games_excess(self) -> dict:
        pass


class Roulette(IconScoreBase):
    _EXCESS = "house_excess"
    _EXCESS_TO_DISTRIBUTE = "excess_to_distribute"

    _TOTAL_DISTRIBUTED = "total_distributed"
    _GAME_ON = "game_on"

    _BET_TYPE = "bet_type"
    _TREASURY_MIN = "treasury_min"
    _BET_LIMITS = "bet_limits"
    _DAY = "day"
    _SKIPPED_DAYS = "skipped_days"
    _DAILY_BET_COUNT = "daily_bet_count"
    _TOTAL_BET_COUNT = "total_bet_count"
    _YESTERDAYS_BET_COUNT = "yesterdays_bet_count"
    _TOKEN_SCORE = "token_score"
    _REWARDS_SCORE = "rewards_score"
    _DIVIDENDS_SCORE = "dividends_score"

    _VOTE = "vote"
    _VOTED = "voted"
    _YES_VOTES = "yes_votes"
    _NO_VOTES = "no_votes"
    _OPEN_TREASURY = "open_treasury"
    _GAME_AUTH_SCORE = "game_auth_score"

    _NEW_DIV_LIVE = "new_div_live"
    _TREASURY_BALANCE = "treasury_balance"

    _EXCESS_SMOOTHING_LIVE = "excess_smoothing_live"

    _DAOFUND_SCORE = "daofund_score"
    _YESTERDAYS_EXCESS = "yesterdays_excess"
    _DAOFUND_TO_DISTRIBUTE = "daofund_to_distribute"

    @eventlog(indexed=2)
    def FundTransfer(self, recipient: Address, amount: int, note: str):
        pass

    @eventlog(indexed=2)
    def FundReceived(self, sender: Address, amount: int, note: str):
        pass

    @eventlog(indexed=2)
    def BetSource(self, _from: Address, timestamp: int):
        pass

    @eventlog(indexed=2)
    def BetPlaced(self, amount: int, numbers: str):
        pass

    @eventlog(indexed=2)
    def BetResult(self, spin: str, winningNumber: str, payout: int):
        pass

    @eventlog(indexed=3)
    def DayAdvance(self, day: int, skipped: int, block_time: int, note: str):
        pass

    @eventlog(indexed=2)
    def Vote(self, _from: Address, _vote: str, note: str):
        pass

    def __init__(self, db: IconScoreDatabase) -> None:
        super().__init__(db)
        Logger.debug(f'In __init__.', TAG)
        Logger.debug(f'owner is {self.owner}.', TAG)
        self._excess = VarDB(self._EXCESS, db, value_type=int)
        self._total_distributed = VarDB(self._TOTAL_DISTRIBUTED, db, value_type=int)
        self._game_on = VarDB(self._GAME_ON, db, value_type=bool)
        self._bet_type = VarDB(self._BET_TYPE, db, value_type=str)
        self._treasury_min = VarDB(self._TREASURY_MIN, db, value_type=int)
        self._bet_limits = DictDB(self._BET_LIMITS, db, value_type=int)
        self._day = VarDB(self._DAY, db, value_type=int)
        self._skipped_days = VarDB(self._SKIPPED_DAYS, db, value_type=int)
        self._total_bet_count = VarDB(self._TOTAL_BET_COUNT, db, value_type=int)
        self._daily_bet_count = VarDB(self._DAILY_BET_COUNT, db, value_type=int)
        self._yesterdays_bet_count = VarDB(self._YESTERDAYS_BET_COUNT, db, value_type=int)
        self._token_score = VarDB(self._TOKEN_SCORE, db, value_type=Address)
        self._rewards_score = VarDB(self._REWARDS_SCORE, db, value_type=Address)
        self._dividends_score = VarDB(self._DIVIDENDS_SCORE, db, value_type=Address)

        self._vote = DictDB(self._VOTE, db, value_type=str)
        self._voted = ArrayDB(self._VOTED, db, value_type=Address)
        self._yes_votes = VarDB(self._YES_VOTES, db, value_type=int)
        self._no_votes = VarDB(self._NO_VOTES, db, value_type=int)
        self._open_treasury = VarDB(self._OPEN_TREASURY, db, value_type=bool)
        self._game_auth_score = VarDB(self._GAME_AUTH_SCORE, db, value_type=Address)

        self._new_div_live = VarDB(self._NEW_DIV_LIVE, db, value_type=bool)
        self._excess_to_distribute = VarDB(self._EXCESS_TO_DISTRIBUTE, db, value_type=int)
        self._treasury_balance = VarDB(self._TREASURY_BALANCE, db, value_type=int)

        self._excess_smoothing_live = VarDB(self._EXCESS_SMOOTHING_LIVE, db, value_type=bool)

        self._daofund_score = VarDB(self._DAOFUND_SCORE, db, value_type=Address)
        self._yesterdays_excess = VarDB(self._YESTERDAYS_EXCESS, db, value_type=int)
        self._daofund_to_distirbute = VarDB(self._DAOFUND_TO_DISTRIBUTE, db, value_type=int)

    def on_install(self) -> None:
        super().on_install()
        self._excess.set(0)
        self._total_distributed.set(0)
        self._game_on.set(False)
        self._bet_type.set(BET_TYPES[0])
        self._treasury_min.set(TREASURY_MINIMUM)
        self._set_bet_limit()
        self._day.set(self.now() // U_SECONDS_DAY)
        self._skipped_days.set(0)
        self._total_bet_count.set(0)
        self._daily_bet_count.set(0)
        self._yesterdays_bet_count.set(0)
        self._yes_votes.set(0)
        self._no_votes.set(0)
        self._open_treasury.set(False)
        self._game_auth_score.set(0)

    def on_update(self) -> None:
        super().on_update()
        self._daofund_score.set(Address.from_string("cx3efe110f76be1c223547f4c1a62dcc681f11af34"))
        self._yesterdays_excess.set(0)
        self._daofund_to_distirbute.set(0)

    @external
    def toggle_excess_smoothing(self) -> None:
        """
        Toggles the status of excess smoothing between true and false. If its true, it keeps the 10% of excess to be
        distributed to tap holders and wager war in the treasury itself making a positive start for next day. If false,
        the feature is disabled
        :return:
        """
        if self.msg.sender != self.owner:
            revert("This method can only be invoked by the score owner. You are trying for unauthorized access")
        self._excess_smoothing_live.set(not self._excess_smoothing_live.get())

    @external(readonly=True)
    def get_excess_smoothing_status(self) -> bool:
        """
        Status of excess smoothing.
        :return: Returns the boolean value representing the status of excess smoothing
        """
        return self._excess_smoothing_live.get()

    @external
    def set_token_score(self, _score: Address) -> None:
        """
        Sets the token score address. Only owner can set the address.
        :param _score: Address of the token score
        :type _score: :class:`iconservice.base.address.Address`
        :return:
        """
        if self.msg.sender == self.owner:
            self._token_score.set(_score)

    @external(readonly=True)
    def get_token_score(self) -> Address:
        """
        Returns the token score address
        :return: TAP token score address
        :rtype: :class:`iconservice.base.address.Address`
        """
        return self._token_score.get()

    @external
    def set_rewards_score(self, _score: Address) -> None:
        """
        Sets the rewards score address. Only owner can set the address.
        :param _score: Address of the rewards score
        :type _score: :class:`iconservice.base.address.Address`
        :return:
        """
        if self.msg.sender == self.owner:
            self._rewards_score.set(_score)

    @external(readonly=True)
    def get_rewards_score(self) -> Address:
        """
        Returns the rewards score address
        :return: Rewards score address
        :rtype: :class:`iconservice.base.address.Address`
        """
        return self._rewards_score.get()

    @external
    def set_dividends_score(self, _score: Address) -> None:
        """
        Sets the dividends score address. Only owner can set the address.
        :param _score: Address of the dividends score address
        :type _score: :class:`iconservice.base.address.Address`
        :return:
        """
        if self.msg.sender == self.owner:
            self._dividends_score.set(_score)

    @external(readonly=True)
    def get_dividends_score(self) -> Address:
        """
        Returns the dividends score address
        :return: Dividends score address
        :rtype: :class:`iconservice.base.address.Address`
        """
        return self._dividends_score.get()

    @external
    def set_game_auth_score(self, _score: Address) -> None:
        """
        Sets the game authorization score address. Only owner can set this address
        :param _score: Address of the game authorization score
        :type _score: :class:`iconservice.base.address.Address`
        :return:
        """
        if self.msg.sender == self.owner:
            self._game_auth_score.set(_score)

    @external(readonly=True)
    def get_game_auth_score(self) -> Address:
        """
        Returns the game authorization score address
        :return: Game authorization score address
        :rtype: :class:`iconservice.base.address.Address`
        """
        return self._game_auth_score.get()

    @external(readonly=True)
    def get_treasury_status(self) -> bool:
        """
        Returns the status of treasury. If the treasury is to be dissolved it returns True
        :return: True if treasury is to be dissolved
        :rtype: bool
        """
        return self._open_treasury.get()

    @external
    @payable
    def set_treasury(self) -> None:
        """
        Anyone can add amount to the treasury and increase the treasury minimum
        Receives the amount and updates the treasury minimum value.
        Can increase treasury minimum with multiples of 10,000 ICX
        :return:
        """
        if self.msg.value < 10**22:
            revert("set_treasury method doesnt accept ICX less than 10000 ICX")
        if self.msg.value % 10**22 != 0:
            revert("Set treasury error, Please send amount in multiples of 10,000 ICX")
        self._treasury_min.set(self._treasury_min.get() + self.msg.value)
        Logger.debug(f'Increasing treasury minimum by {self.msg.value} to {self._treasury_min.get()}.')
        self._set_bet_limit()
        self._open_treasury.set(False)
        self.FundReceived(self.msg.sender, self.msg.value, f"Treasury minimum increased by {self.msg.value}")
        Logger.debug(f'{self.msg.value} was added to the treasury from address {self.msg.sender}', TAG)

    def _set_bet_limit(self) -> None:
        """
        Sets the bet limits for the new treasury minimum
        :return:
        """
        for i, ratio in enumerate(BET_LIMIT_RATIOS):
            self._bet_limits[i] = self._treasury_min.get() // ratio

    @external
    def game_on(self) -> None:
        """
        Turns on the game. Only owner can turn on the game
        :return:
        """
        if self.msg.sender != self.owner:
            revert(f'Only the game owner can turn it on.')
        if not self._game_on.get():
            self._game_on.set(True)
            self._day.set(self.now() // U_SECONDS_DAY)

    @external
    def game_off(self) -> None:
        """
        Turns off the game. Only owner can turn off the game
        :return:
        """
        if self.msg.sender != self.owner:
            revert("Only the score owner can turn it off")
        if self._game_on.get():
            self._game_on.set(False)

    @external(readonly=True)
    def get_game_on_status(self) -> bool:
        """
        Returns the status of the game.
        :return: Status of game
        :rtype: bool
        """
        return self._game_on.get()

    @external(readonly=True)
    def get_multipliers(self) -> str:
        """
        Returns the multipliers of different bet types
        :return: Multipliers of different bet types
        :rtype: str
        """
        return str(MULTIPLIERS)

    @external(readonly=True)
    def get_excess(self) -> int:
        """
        Returns the reward pool of the ICONbet platform
        :return: Reward pool of the ICONbet platform
        :rtype: int
        """
        excess_to_min_treasury = self._treasury_balance.get() - self._treasury_min.get()
        auth_score = self.create_interface_score(self._game_auth_score.get(), AuthInterface)
        div_score = self.create_interface_score(self._dividends_score.get(), DividendsInterface)
        if not self._excess_smoothing_live.get():
            return excess_to_min_treasury - auth_score.get_excess()
        else:
            third_party_games_excess: int = 0
            games_excess = auth_score.get_todays_games_excess()
            inhouse_games = div_score.get_inhouse_games()
            for game in games_excess:
                address = Address.from_string(game)
                if address not in inhouse_games:
                    third_party_games_excess += max(0, int(games_excess[game]))
            reward_pool = excess_to_min_treasury - third_party_games_excess * 20//100
            return reward_pool

    @external(readonly=True)
    def get_total_distributed(self) -> int:
        """
        Returns the total distributed amount from the platform
        :return: Total distributed excess amount
        :rtype: int
        """
        return self._total_distributed.get()

    @external(readonly=True)
    def get_total_bets(self) -> int:
        """
        Returns the total bets made till date
        :return: Total bets made till date
        :rtype: int
        """
        return self._total_bet_count.get() + self._daily_bet_count.get()

    @external(readonly=True)
    def get_todays_bet_total(self) -> int:
        """
        Returns the total bets of current day
        :return: Total bets of current day
        :rtype: int
        """
        return self._daily_bet_count.get()

    @external(readonly=True)
    def get_treasury_min(self) -> int:
        """
        Returns the treasury minimum value
        :return: Treasury minimum value
        :rtype: int
        """
        return self._treasury_min.get()

    @external(readonly=True)
    def get_bet_limit(self, n: int) -> int:
        """
        Returns the bet limit for the number of selected numbers
        :param n: No. of selected numbers
        :type n: int
        :return: Bet limit in loop
        :rtype: int
        """
        return self._bet_limits[n]

    @external(readonly=True)
    def get_vote_results(self) -> str:
        """
        Returns the vote results of dissolving the treasury.
        :return: Vote result for treasury to be dissolved e.g. [0,0]
        :rtype: str
        """
        results = [self._yes_votes.get(), self._no_votes.get()]
        return str(results)

    @external(readonly=True)
    def get_score_owner(self) -> Address:
        """
        A function to return the owner of this score.
        :return: Owner address of this score
        :rtype: :class:`iconservice.base.address.Address`
        """
        return self.owner

    @external(readonly=True)
    def get_skipped_days(self) -> int:
        """
        Returns the number of skipped days. Days are skipped if the distribution is not completed in any previous day.
        :return: Number of skipped days
        :rtype: int
        """
        return self._skipped_days.get()

    @external(readonly=True)
    def get_yesterdays_excess(self) -> int:
        return self._yesterdays_excess.get()

    @external(readonly=True)
    def get_daofund_score(self) -> Address:
        return self._daofund_score.get()

    @external
    def set_daofund_score(self, _score: Address) -> None:
        if self.msg.sender != self.owner:
            revert("TREASURY: DAOfund address can only be set by owner")
        if not _score.is_contract:
            revert("TREASURY: Only contract address is accepted for DAOfund")
        self._daofund_score.set(_score)

    @external
    @payable
    def send_wager(self,_amount:int):
        if self.msg.value != _amount:
            revert('ICX sent and the amount in the parameters are not same')
        self._take_wager(self.msg.sender, _amount)

    @external
    @payable
    def send_rake(self,_wager: int, _payout: int):
        if self.msg.value != (_wager - _payout):
            revert('ICX sent and the amount in the parameters are not same')
        self.take_rake(_wager, _payout)

    @external
    def take_wager(self, _amount: int) -> None:
        """
        Takes wager amount from approved games. The wager amounts are recorded in game authorization score. Checks if
        the day has been advanced. If the day has advanced the excess amount is transferred to distribution contract.
        :param _amount: Wager amount to be recorded for excess calculation
        :return:
        """
        self._take_wager(self.msg.sender, _amount)

    def _take_wager(self, _game_address: Address, _amount: int) -> None:
        """
        Takes wager amount from approved games.
        :param _game_address: Address of the game
        :type _game_address: :class:`iconservice.base.address.Address`
        :param _amount: Wager amount
        :type _amount: int
        :return:
        """
        if _amount <= 0:
            revert(f"Invalid bet amount {_amount}")
        auth_score = self.create_interface_score(self._game_auth_score.get(), AuthInterface)
        if auth_score.get_game_status(_game_address) != "gameApproved":
            revert(f'Bet only accepted through approved games.')
        if self.__day_advanced():
            self.__check_for_dividends()
        self._daily_bet_count.set(self._daily_bet_count.get() + 1)
        auth_score.accumulate_daily_wagers(_game_address, _amount)
        Logger.debug(f'Sending wager data to rewards score.', TAG)
        rewards_score = self.create_interface_score(self._rewards_score.get(), RewardsInterface)
        rewards_score.accumulate_wagers(str(self.tx.origin), _amount, (self._day.get() - self._skipped_days.get()) % 2)
        self._treasury_balance.set( self.icx.get_balance(self.address))

    @external
    def take_rake(self, _wager: int, _payout: int) -> None:
        """
        Takes wager amount and payout amount data from games which have their own treasury.
        :param _wager: Wager you want to record in GAS
        :param _payout: Payout you want to record
        :return:
        """
        if _payout <= 0:
            revert("Payout can't be zero")
        self._take_wager(self.msg.sender, _wager)

        # dry run of wager_payout i.e. make payout without sending ICX
        auth_score = self.create_interface_score(self._game_auth_score.get(), AuthInterface)
        if auth_score.get_game_status(self.msg.sender) != "gameApproved":
            revert('Payouts can only be invoked by approved games.')
        auth_score.accumulate_daily_payouts(self.msg.sender, _payout)
        self._treasury_balance.set(self.icx.get_balance(self.address))

    @external
    def wager_payout(self, _payout: int) -> None:
        """
        Makes payout to the player of the approved games. Only the approved games can request payout.
        :param _payout: Payout to be made to the player
        :return:
        """
        self._wager_payout(self.msg.sender, _payout)

    def _wager_payout(self, _game_address: Address, _payout: int):
        """
        Makes payout to the player of the approved games.
        :param _game_address: Address of the game requesting payout
        :type _game_address: :class:`iconservice.base.address.Address`
        :param _payout: Payout to be made to the player
        :type _payout: int
        :return:
        """
        if _payout <= 0:
            revert(f"Invalid payout amount requested {_payout}")
        auth_score = self.create_interface_score(self._game_auth_score.get(), AuthInterface)
        if auth_score.get_game_status(_game_address) != "gameApproved":
            revert(f'Payouts can only be invoked by approved games.')
        try:
            Logger.debug(f'Trying to send to ({self.tx.origin}): {_payout}.', TAG)
            self.icx.transfer(self.tx.origin, _payout)
            self.FundTransfer(self.tx.origin, _payout, f'Player Winnings from {self.msg.sender}.')
            auth_score.accumulate_daily_payouts(_game_address, _payout)
            Logger.debug(f'Sent winner ({self.tx.origin}) {_payout}.', TAG)
        except BaseException as e:
            Logger.debug(f'Send failed. Exception: {e}', TAG)
            revert('Network problem. Winnings not sent. Returning funds. '
                   f'Exception: {e}')
        self._treasury_balance.set(self.icx.get_balance(self.address))

    @external
    @payable
    def bet_on_numbers(self, numbers: str, user_seed: str = '') -> None:
        """
        Takes a list of numbers in the form of a comma separated string. e.g. "1,2,3,4" and user seed
        :param numbers: Numbers selected
        :type numbers: str
        :param user_seed: User seed/ Lucky phrase provided by user which is used in random number calculation
        :type user_seed: str
        :return:
        """
        numset = set(numbers.split(','))
        if numset == SET_RED or numset == SET_BLACK:
            self._bet_type.set(BET_TYPES[2])
        elif numset == SET_ODD or numset == SET_EVEN:
            self._bet_type.set(BET_TYPES[3])
        else:
            self._bet_type.set(BET_TYPES[1])
        self.__bet(numbers, user_seed)

    @external
    @payable
    def bet_on_color(self, color: bool, user_seed: str = '') -> None:
        """
        The bet is set on either red color or black color.
        :param color: Red Color is chosen if true. Black if false
        :type color: blue
        :param user_seed: User seed/ Lucky phrase provided by user which is used in random number calculation
        :type user_seed: str
        :return:
        """
        self._bet_type.set(BET_TYPES[2])
        if color:
            numbers = WHEEL_RED
        else:
            numbers = WHEEL_BLACK
        self.__bet(numbers, user_seed)

    @external
    @payable
    def bet_on_even_odd(self, even_odd: bool, user_seed: str = '') -> None:
        """
        The bet is set on either odd or even numbers.
        :param even_odd: Odd numbers is chosen if true. Even if false.
        :type even_odd: bool
        :param user_seed: User seed/ Lucky phrase provided by user which is used in random number calculation
        :type user_seed: str
        :return:
        """
        self._bet_type.set(BET_TYPES[3])
        if even_odd:
            numbers = WHEEL_ODD
        else:
            numbers = WHEEL_EVEN
        self.__bet(numbers, user_seed)

    @external
    def untether(self) -> None:
        """
        A function to redefine the value of self.owner once it is possible.
        To be included through an update if it is added to IconService.
        Sets the value of self.owner to the score holding the game treasury.
        """
        if self.msg.sender != self.owner:
            revert(f'Only the owner can call the untether method.')
        pass

    @external
    def vote(self, option: str) -> None:
        """
        Vote takes the votes from TAP holders to dissolve the treasury.
        :param option: Option to select for dissolving the treasury ("yes" | "no")
        :type option: str
        :return:
        """
        if option not in ['yes', 'no']:
            revert(f'Option must be one of either "yes" or "no".')
        token_score = self.create_interface_score(self._token_score.get(), TokenInterface)
        address = self.tx.origin
        if address not in self._voted and token_score.balanceOf(address) == 0:
            revert(f'You must either own or be a previous owner of TAP tokens in order to cast a vote.')
        self._vote[str(address)] = option
        if address not in self._voted:
            self._voted.put(address)
            message = f"Recorded vote of {str(address)}"
            self.Vote(self.msg.sender, option, message)
        else:
            message = f"{str(address)} updated vote to {option}"
            self.Vote(address, option, message)
        if not self.vote_result():
            vote_msg = "Overall Vote remains a 'No'."
            self.Vote(address, option, vote_msg)
        else:
            # In case the votes is passed, treasury is dissolved by sending all the balance to distribution contract.
            # Distribution contract will then distribute 80% to tap holders and 20% to founders.
            self._open_treasury.set(True)
            self._excess_to_distribute.set(self.icx.get_balance(self.address))
            self.__check_for_dividends()
            vote_msg = "Vote passed! Treasury balance forwarded to distribution contract."
            self.Vote(address, option, vote_msg)
            self._treasury_min.set(0)

    def vote_result(self) -> bool:
        """
        Returns the vote result of vote on dissolving the treasury
        :return: True if majority of votes are yes
        :rtype: bool
        """
        token_score = self.create_interface_score(self._token_score.get(), TokenInterface)
        yes = 0
        no = 0
        for address in self._voted:
            vote = self._vote[str(address)]
            if vote == 'yes':
                yes += token_score.balanceOf(address)
            else:
                no += token_score.balanceOf(address)
        self._yes_votes.set(yes)
        self._no_votes.set(no)
        if self._yes_votes.get() > (token_score.totalSupply() - token_score.balanceOf(self._rewards_score.get())) // 2:
            return True
        else:
            return False

    @external(readonly=True)
    def get_batch_size(self, recip_count: int) -> int:
        """
        Returns the batch size to be used for distribution according to the number of recipients. Minimum batch size is
        10 and maximum is 500.
        :param recip_count: Number of recipients
        :type recip_count: int
        :return: Batch size
        :rtype: int
        """
        Logger.debug(f'In get_batch_size.', TAG)
        yesterdays_count = self._yesterdays_bet_count.get()
        if yesterdays_count < 1:
            yesterdays_count = 1
        size = (DIST_DURATION_PARAM * recip_count // yesterdays_count)
        if size < TX_MIN_BATCH_SIZE:
            size = TX_MIN_BATCH_SIZE
        if size > TX_MAX_BATCH_SIZE:
            size = TX_MAX_BATCH_SIZE
        Logger.debug(f'Returning batch size of {size}', TAG)
        return size

    def get_random(self, user_seed: str = '') -> float:
        """
        Generates a random # from tx hash, block timestamp and user provided
        seed. The block timestamp provides the source of unpredictability.
        :param user_seed: 'Lucky phrase' provided by user.
        :type user_seed: str
        :return: number from [x / 100000.0 for x in range(100000)] i.e. [0,0.99999]
        :rtype: float
        """
        Logger.debug(f'Entered get_random.', TAG)
        seed = (str(bytes.hex(self.tx.hash)) + str(self.now()) + user_seed)
        spin = (int.from_bytes(sha3_256(seed.encode()), "big") % 100000) / 100000.0
        Logger.debug(f'Result of the spin was {spin}.', TAG)
        return spin

    def __day_advanced(self) -> bool:
        """
        Checks if day has been advanced nad the TAP distribution as well as dividends distribution has been completed.
        If the day has advanced and the distribution has completed then the current day is updated, excess is recorded
        from game authorization score, total bet count is updated and the daily bet count is reset.
        :return: True if day has advanced and distribution has been completed for previous day
        :rtype: bool
        """
        Logger.debug(f'In __day_advanced method.', TAG)
        currentDay = self.now() // U_SECONDS_DAY
        advance = currentDay - self._day.get()
        if advance < 1:
            return False
        else:
            rewards_score = self.create_interface_score(self._rewards_score.get(), RewardsInterface)
            dividends_score = self.create_interface_score(self._dividends_score.get(), DividendsInterface)
            auth_score = self.create_interface_score(self._game_auth_score.get(), AuthInterface)
            rewards_complete = rewards_score.rewards_dist_complete()
            dividends_complete = dividends_score.dividends_dist_complete()
            if not rewards_complete or not dividends_complete:
                rew = ""
                div = ""
                if not rewards_complete:
                    rew = " Rewards dist is not complete"
                if not dividends_complete:
                    div = " Dividends dist is not complete"
                self._day.set(currentDay)
                self._skipped_days.set(self._skipped_days.get() + advance)
                self.DayAdvance(self._day.get(), self._skipped_days.get(), self.now(),
                                f'Skipping a day since{rew}{div}')
                return False

            # Set excess to distribute
            excess_to_min_treasury = self._treasury_balance.get() - self._treasury_min.get()
            developers_excess = auth_score.record_excess()
            self._excess_to_distribute.set(developers_excess + max(0, excess_to_min_treasury - developers_excess))

            if self._excess_smoothing_live.get():
                third_party_games_excess: int = 0
                games_excess = auth_score.get_yesterdays_games_excess()
                inhouse_games = dividends_score.get_inhouse_games()
                for game in games_excess:
                    address = Address.from_string(game)
                    if address not in inhouse_games:
                        third_party_games_excess += max(0, int(games_excess[game]))
                partner_developer = third_party_games_excess*20//100
                reward_pool = max(0, (excess_to_min_treasury - partner_developer)*90//100)
                daofund = max(0, (excess_to_min_treasury - partner_developer)*5//100)
                self._excess_to_distribute.set(partner_developer + reward_pool)
                self._yesterdays_excess.set(excess_to_min_treasury - partner_developer)
                self._daofund_to_distirbute.set(daofund)

            if advance > 1:
                self._skipped_days.set(self._skipped_days.get() + advance - 1)

            self._day.set(currentDay)
            self._total_bet_count.set(self._total_bet_count.get() + self._daily_bet_count.get())
            self._yesterdays_bet_count.set(self._daily_bet_count.get())
            self._daily_bet_count.set(0)
            self.DayAdvance(self._day.get(), self._skipped_days.get(), self.now(), "Day advanced. Counts reset.")
            return True

    def __check_for_dividends(self) -> None:
        """
        If there is excess in the treasury, transfers to the distribution contract.
        :return:
        """
        excess = self._excess_to_distribute.get()
        daofund = self._daofund_to_distirbute.get()

        Logger.debug(f'Found treasury excess of {excess}.', TAG)
        if excess > 0:
            try:
                Logger.debug(f'Trying to send to ({self._dividends_score.get()}): {excess}.', TAG)
                self.icx.transfer(self._dividends_score.get(), excess)
                self.FundTransfer(self._dividends_score.get(), excess, "Excess made by games")
                Logger.debug(f'Sent div score ({self._dividends_score.get()}) {excess}.', TAG)
                self._total_distributed.set(self._total_distributed.get() + excess)
                self._excess_to_distribute.set(0)
            except BaseException as e:
                Logger.debug(f'Send failed. Exception: {e}', TAG)
                revert('Network problem. Excess not sent. '
                       f'Exception: {e}')

        if daofund > 0:
            try:
                self._daofund_to_distirbute.set(0)
                self.icx.transfer(self._daofund_score.get(), daofund)
                self.FundTransfer(self._daofund_score.get(), daofund, "Excess transerred to daofund")
            except BaseException as e:
                revert('Network problem. DAOfund not sent. '
                       f'Exception: {e}')

    def __bet(self, numbers: str, user_seed: str) -> None:
        """
        Takes a list of numbers in the form of a comma separated string and the user seed
        :param numbers: The numbers which are selected for the bet
        :type numbers: str
        :param user_seed: User seed/ Lucky phrase provided by user which is used in random number calculation
        :type user_seed: str
        :return:
        """
        self.BetSource(self.tx.origin, self.tx.timestamp)
        if not self._game_on.get():
            Logger.debug(f'Game not active yet.', TAG)
            revert(f'Game not active yet.')
        amount = self.msg.value
        Logger.debug(f'Betting {amount} loop on {numbers}.', TAG)
        self.BetPlaced(amount, numbers)
        self._take_wager(self.address, amount)

        nums = set(numbers.split(','))
        n = len(nums)
        if n == 0:
            Logger.debug(f'Bet placed without numbers.', TAG)
            revert(f' Invalid bet. No numbers submitted. Zero win chance. Returning funds.')
        elif n > 20:
            Logger.debug(f'Bet placed with too many numbers. Max numbers = 20.', TAG)
            revert(f' Invalid bet. Too many numbers submitted. Returning funds.')

        numset = set(WHEEL_ORDER)
        numset.remove('0')
        for num in nums:
            if num not in numset:
                Logger.debug(f'Invalid number submitted.', TAG)
                revert(f' Please check your bet. Numbers must be between 0 and 20, submitted as a comma separated '
                       f'string. Returning funds.')

        bet_type = self._bet_type.get()
        self._bet_type.set(BET_TYPES[0])
        if bet_type == BET_TYPES[2] or bet_type == BET_TYPES[3]:
            bet_limit = self._bet_limits[0]
        else:
            bet_limit = self._bet_limits[n]
        if amount < BET_MIN or amount > bet_limit:
            Logger.debug(f'Betting amount {amount} out of range.', TAG)
            revert(f'Betting amount {amount} out of range ({BET_MIN} -> {bet_limit} loop).')

        if n == 1:
            bet_type = BET_TYPES[4]
        if bet_type == BET_TYPES[1]:
            payout = int(MULTIPLIERS[BET_TYPES[5]] * 1000) * amount // (1000 * n)
        else:
            payout = MULTIPLIERS[bet_type] * amount
        if self.icx.get_balance(self.address) < payout:
            Logger.debug(f'Not enough in treasury to make the play.', TAG)
            revert('Not enough in treasury to make the play.')

        spin = self.get_random(user_seed)
        winningNumber = WHEEL_ORDER[int(spin * 21)]
        Logger.debug(f'winningNumber was {winningNumber}.', TAG)
        win = winningNumber in nums
        payout = payout * win
        self.BetResult(str(spin), winningNumber, payout)

        if win == 1:
            self._wager_payout(self.address, payout)
        else:
            Logger.debug(f'Player lost. ICX retained in treasury.', TAG)

    @payable
    @external
    def add_to_excess(self) -> None:
        """
        Users can add to excess, excess added by this method will be only shared to tap holders and wager wars
        :return:
        """
        if self.msg.value <= 0:
            revert("No amount added to excess")
        self._treasury_balance.set(self.icx.get_balance(self.address))
        self.FundReceived(self.msg.sender, self.msg.value, f"{self.msg.value} added to excess")

    @payable
    def fallback(self):
        auth_score = self.create_interface_score(self._game_auth_score.get(), AuthInterface)
        if auth_score.get_game_status(self.msg.sender) != "gameApproved":
            revert(
                f'This score accepts plain ICX through approved games and through set_treasury, add_to_excess method.')